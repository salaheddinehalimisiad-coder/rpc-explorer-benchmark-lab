"""Tests du streaming serveur -> client du Custom RPC."""

import io
import time
import unittest
from contextlib import redirect_stdout

from business.inventory_service import InventoryService
from lab.servers import build_custom_server
from rpc_core import RPCClient, RPCError, RPCServer
from under_the_hood import RPCTracer


class TestBusinessIterator(unittest.TestCase):
    def test_iter_matches_list(self):
        s = InventoryService()
        a = [e["value"] for e in s.stream_analytics("memory_usage", 5)]
        b = [e["value"] for e in s.stream_analytics_iter("memory_usage", 5)]
        self.assertEqual(a, b)

    def test_validation_is_immediate(self):
        with self.assertRaises(ValueError):
            InventoryService().stream_analytics_iter("nope", 3)
        with self.assertRaises(ValueError):
            InventoryService().stream_analytics_iter("cpu_usage", 3, interval_ms=-1)


class TestCustomStreaming(unittest.TestCase):
    def setUp(self):
        self.tracer = RPCTracer()
        self.server = build_custom_server(InventoryService(), tracer=self.tracer)
        self.server.start()
        self.client = RPCClient(port=self.server.port, timeout=3)

    def tearDown(self):
        self.server.stop()

    def test_stream_yields_all_items_in_order(self):
        items = list(self.client.stream("stream_analytics", metric_name="cpu_usage", num_events=6))
        self.assertEqual([e["sequence"] for e in items], [1, 2, 3, 4, 5, 6])

    def test_unary_call_still_returns_list(self):
        res = self.client.stream_analytics(metric_name="cpu_usage", num_events=3)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 3)

    def test_first_item_arrives_before_the_end(self):
        t0 = time.perf_counter()
        it = self.client.stream("stream_analytics", metric_name="cpu_usage", num_events=5, interval_ms=100)
        next(it)
        first = time.perf_counter() - t0
        rest = list(it)
        total = time.perf_counter() - t0
        self.assertEqual(len(rest), 4)
        self.assertLess(first, 0.08)
        self.assertGreater(total, 0.35)

    def test_non_stream_method(self):
        with self.assertRaises(RPCError) as ctx:
            list(self.client.stream("calculate_factorial", n=3))
        self.assertEqual(ctx.exception.code, "STREAM_NOT_SUPPORTED")

    def test_invalid_arguments(self):
        with self.assertRaises(RPCError) as ctx:
            list(self.client.stream("stream_analytics", metric_name="cpu_usage", bogus=1))
        self.assertEqual(ctx.exception.code, "INVALID_ARGS")
        with self.assertRaises(RPCError) as ctx:
            list(self.client.stream("stream_analytics", metric_name="unknown"))
        self.assertEqual(ctx.exception.code, "EXECUTION_ERROR")

    def test_error_in_the_middle_of_the_stream(self):
        def faulty():
            yield 1
            yield 2
            raise RuntimeError("capteur débranché")

        self.server.register_stream("faulty", faulty)
        got = []
        with self.assertRaises(RPCError) as ctx:
            for x in self.client.stream("faulty"):
                got.append(x)
        self.assertEqual(got, [1, 2])
        self.assertEqual(ctx.exception.data["items_sent"], 2)

    def test_server_stops_when_client_leaves(self):
        it = self.client.stream("stream_analytics", metric_name="cpu_usage", num_events=50, interval_ms=20)
        next(it), next(it)
        it.close()  # le client arrête d'écouter (ferme sa connexion)
        time.sleep(0.6)
        steps = [e["step"] for e in self.tracer.get_trace()]
        self.assertIn("STREAM_ABORT (client parti)", steps)
        sent = sum(1 for s in steps if s.startswith("STREAM_SEND"))
        self.assertLess(sent, 50)

    def test_connection_reused_after_stream(self):
        # la même connexion serveur peut traiter une requête normale après un flux
        server = RPCServer(port=0)
        server.register_stream("nums", lambda: iter([1, 2]))
        server.register_method("ping", lambda: "pong")
        server.start()
        try:
            c = RPCClient(port=server.port, persistent=True)
            self.assertEqual(list(c.stream("nums")), [1, 2])
            self.assertEqual(c.ping(), "pong")
            c.close()
        finally:
            server.stop()


class TestStreamingDemo(unittest.TestCase):
    def test_demo_measures_time_to_first_item(self):
        from lab.streaming import run_streaming_demo
        with redirect_stdout(io.StringIO()):
            res = run_streaming_demo(num_events=4, interval_ms=80)
        self.assertGreater(res["unique"]["premier_ms"], 200)
        self.assertLess(res["stream"]["premier_ms"], 60)
        self.assertEqual(res["stream"]["messages"], 5)


if __name__ == "__main__":
    unittest.main()
