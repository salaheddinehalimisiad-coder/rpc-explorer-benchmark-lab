"""Tests de l'API du tableau de bord web (client de test Flask, vrais serveurs RPC)."""

import unittest

from dashboard.app import Dashboard


class TestDashboardAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dash = Dashboard().start()
        cls.c = cls.dash.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.dash.stop()

    def setUp(self):
        self.c.post("/api/faults", json={"kind": "reset"})

    def call(self, protocol, method, **args):
        return self.c.post("/api/call", json={"protocol": protocol, "method": method, "args": args}).json

    def test_index_and_info(self):
        self.assertIn(b"RPC Explorer", self.c.get("/").data)
        info = self.c.get("/api/info").json
        self.assertEqual(set(info["servers"]), {"custom", "grpc", "rest"})
        self.assertIn("update_stock", info["methods"])

    def test_custom_call_returns_trace(self):
        r = self.call("custom", "calculate_factorial", n=6)
        self.assertEqual((r["status"], r["result"]), ("OK", 720))
        steps = [s["step"] for s in r["trace"]]
        self.assertIn("EXECUTE (fonction métier locale)", steps)

    def test_grpc_call_returns_decoded_bytes(self):
        r = self.call("grpc", "calculate_factorial", n=5)
        self.assertEqual(r["grpc"]["request"]["hex"], "08 05")
        self.assertEqual(r["grpc"]["request"]["fields"][0]["name"], "n")

    def test_rest_call_returns_raw_http(self):
        r = self.call("rest", "get_product_details", item_id="PROD-002")
        self.assertTrue(r["http"]["request"].startswith("GET /api/products/PROD-002 HTTP/1.1"))
        self.assertEqual(r["result"]["item_id"], "PROD-002")

    def test_errors_are_reported_not_raised(self):
        self.assertEqual(self.call("custom", "calculate_factorial", n=-1)["status"], "EXECUTION_ERROR")
        self.assertEqual(self.call("grpc", "get_product_details", item_id="NOPE")["status"], "NOT_FOUND")
        self.assertTrue(self.call("rest", "get_product_details", item_id="NOPE")["status"].startswith("HTTP 404"))
        self.assertEqual(self.c.post("/api/call", json={"protocol": "custom", "method": "rm_rf"}).status_code, 400)

    def test_injected_crash_then_reset(self):
        st = self.c.post("/api/faults", json={"kind": "crash"}).json
        self.assertEqual(st["active_scenario"], "server_crash")
        self.assertEqual(self.call("grpc", "calculate_factorial", n=3)["status"], "UNAVAILABLE")
        self.c.post("/api/faults", json={"kind": "reset"})
        self.assertEqual(self.call("grpc", "calculate_factorial", n=3)["status"], "OK")

    def test_streaming_sse_and_unary(self):
        body = self.c.get("/api/stream?n=3&interval=10").data.decode()
        self.assertEqual(body.count("data: {\"t_ms\""), 4)  # 3 éléments + fin
        self.assertIn("event: end", body)
        u = self.c.post("/api/stream_unary", json={"n": 3, "interval": 10}).json
        self.assertEqual(len(u["items"]), 3)

    def test_benchmark(self):
        b = self.c.post("/api/benchmark", json={"iterations": 20}).json
        self.assertEqual([r["name"] for r in b["results"]][0], "Local")
        self.assertEqual(len(b["results"]), 5)
        self.assertTrue(all(r["error_count"] == 0 for r in b["results"]))

    def test_experiment(self):
        d = self.c.post("/api/experiment/idempotence").json
        self.assertEqual(d["naif"]["retire"], 2)
        self.assertEqual(self.c.post("/api/experiment/unknown").status_code, 400)

    def test_async_and_typing_experiments(self):
        a = self.c.post("/api/experiment/async").json
        self.assertEqual({r["mode"] for r in a["rows"]}, {"synchrone", "asynchrone"})
        t = self.c.post("/api/experiment/typing").json
        self.assertTrue(all(c["gRPC"]["octets"] == 0 for c in t["cases"]))
        page = self.c.get("/").data
        self.assertIn(b'data-exp="async"', page)
        self.assertIn(b'data-exp="typing"', page)


if __name__ == "__main__":
    unittest.main()
