"""
Tests du mode "Sous le capot" (RPCTracer + hooks du Custom RPC)
et des nouvelles options du client (connexion persistante, appel asynchrone).
"""

import unittest

from business.inventory_service import InventoryService
from rpc_core import RPCClient, RPCServer, RPCError
from under_the_hood import RPCTracer
from under_the_hood.tracer import preview_bytes


class TestTracerUnit(unittest.TestCase):
    def test_record_and_order(self):
        t = RPCTracer()
        t.record_step("A", {"x": 1}, call_id="c1")
        t.record_step("B", {"payload": b'{"a":1}'}, call_id="c1", side="server")
        t.record_step("Z", {}, call_id="c2")
        steps = [e["step"] for e in t.get_trace("c1")]
        self.assertEqual(steps, ["A", "B"])
        text = t.format_trace("c1")
        self.assertIn("SERVEUR", text)
        self.assertIn('{"a":1}', text)
        self.assertEqual(t.call_ids(), ["c1", "c2"])

    def test_disabled_tracer_records_nothing(self):
        t = RPCTracer(enabled=False)
        t.record_step("A")
        self.assertEqual(t.get_trace(), [])

    def test_preview_bytes_binary_is_hex(self):
        self.assertEqual(preview_bytes(b"\x08\x05"), "08 05")
        self.assertEqual(preview_bytes(b"abc"), "abc")


class TestTracedCustomRPC(unittest.TestCase):
    def setUp(self):
        self.tracer = RPCTracer()
        self.server = RPCServer(port=0, tracer=self.tracer)
        self.server.register_service(InventoryService(), ["calculate_factorial", "update_stock"])
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def test_full_cycle_is_traced(self):
        client = RPCClient(port=self.server.port, tracer=self.tracer)
        self.assertEqual(client.calculate_factorial(n=5), 120)
        call_id = self.tracer.call_ids()[0]
        steps = [e["step"] for e in self.tracer.get_trace(call_id)]
        expected_order = [
            "CLIENT_CALL",
            "STUB_MARSHAL + SERIALIZE (JSON)",
            "TRANSPORT_SEND (TCP)",
            "SERVER_RECEIVE + DESERIALIZE",
            "DISPATCH (table blanche)",
            "EXECUTE (fonction métier locale)",
            "SERIALIZE_RESPONSE + TRANSPORT_REPLY",
            "CLIENT_RECEIVE + UNMARSHAL",
            "RESULT -> rendu à l'appelant",
        ]
        self.assertEqual(steps, expected_order)
        sides = {e["step"]: e["side"] for e in self.tracer.get_trace(call_id)}
        self.assertEqual(sides["EXECUTE (fonction métier locale)"], "server")
        self.assertEqual(sides["CLIENT_CALL"], "client")

    def test_unknown_method_is_traced_as_error(self):
        client = RPCClient(port=self.server.port, tracer=self.tracer)
        with self.assertRaises(RPCError):
            client.delete_everything()
        steps = [e["step"] for e in self.tracer.get_trace()]
        self.assertIn("RESULT -> exception levée chez l'appelant", steps)


class TestClientOptions(unittest.TestCase):
    def setUp(self):
        self.server = RPCServer(port=0)
        self.server.register_service(InventoryService(), ["calculate_factorial"])
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def test_persistent_connection_reuses_socket(self):
        with RPCClient(port=self.server.port, persistent=True) as client:
            self.assertEqual(client.calculate_factorial(n=3), 6)
            first_sock = client._sock
            self.assertIsNotNone(first_sock)
            self.assertEqual(client.calculate_factorial(n=4), 24)
            self.assertIs(client._sock, first_sock)
        self.assertIsNone(client._sock)

    def test_persistent_reconnects_after_server_restart(self):
        client = RPCClient(port=self.server.port, persistent=True, timeout=1.0)
        self.assertEqual(client.calculate_factorial(n=3), 6)
        port = self.server.port
        self.server.stop()
        with self.assertRaises((ConnectionError, TimeoutError)):
            client.calculate_factorial(n=3)
        self.server = RPCServer(port=port)
        self.server.register_service(InventoryService(), ["calculate_factorial"])
        self.server.start()
        self.assertEqual(client.calculate_factorial(n=3), 6)
        client.close()

    def test_async_call_returns_future(self):
        with RPCClient(port=self.server.port) as client:
            futures = [client.call_async("calculate_factorial", n=i) for i in range(1, 6)]
            self.assertEqual([f.result(timeout=5) for f in futures], [1, 2, 6, 24, 120])

    def test_async_call_propagates_remote_error(self):
        with RPCClient(port=self.server.port) as client:
            fut = client.call_async("calculate_factorial", n=-1)
            with self.assertRaises(RPCError):
                fut.result(timeout=5)


if __name__ == "__main__":
    unittest.main()
