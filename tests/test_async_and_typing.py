"""Tests des démonstrations « synchrone vs asynchrone » et « typage strict »."""

import io
import unittest
from contextlib import redirect_stdout

from lab.async_demo import run_async_demo
from lab.servers import LabServers
from lab.typing_demo import run_typing_demo


class TestAsyncCalls(unittest.TestCase):
    def test_grpc_future_returns_result(self):
        with LabServers(protocols=["grpc"]) as lab:
            client = lab.grpc_client(timeout=5)
            futures = [client.calculate_factorial_async(n) for n in (3, 4, 5)]
            self.assertEqual([f.result(timeout=5) for f in futures], [6, 24, 120])
            self.assertTrue(all(f.done() for f in futures))

    def test_custom_call_async_returns_result(self):
        with LabServers(protocols=["custom"]) as lab:
            client = lab.custom_client(timeout=5)
            futures = [client.call_async("calculate_factorial", n=n) for n in (3, 4, 5)]
            self.assertEqual([f.result(timeout=5) for f in futures], [6, 24, 120])

    def test_async_overlaps_waits(self):
        with redirect_stdout(io.StringIO()):
            d = run_async_demo(n_calls=4, latency_ms=100)
        by = {(r["protocole"], r["mode"]): r for r in d["rows"]}
        for proto in ("Custom RPC", "gRPC"):
            sync, asyn = by[(proto, "synchrone")], by[(proto, "asynchrone")]
            self.assertEqual(sync["resultats"], asyn["resultats"])  # mêmes résultats
            self.assertGreaterEqual(sync["duree_ms"], 4 * 100 * 0.9)  # attentes additionnées
            self.assertLess(asyn["duree_ms"], sync["duree_ms"] * 0.6)  # attentes superposées


class TestStrictTyping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with redirect_stdout(io.StringIO()):
            cls.cases = run_typing_demo()["cases"]

    def test_grpc_rejects_on_client_before_sending(self):
        for case in self.cases:
            self.assertEqual(case["gRPC"]["octets"], 0, case["cas"])
            self.assertIn("client", case["gRPC"]["ou"])

    def test_json_protocols_send_bytes_and_server_rejects(self):
        for case in self.cases:
            self.assertGreater(case["Custom RPC"]["octets"], 0)
            self.assertIn("serveur", case["Custom RPC"]["ou"])
            self.assertRegex(case["Custom RPC"]["resultat"], r"\(-32\d{3}\)")
            self.assertIn("HTTP 4", case["REST"]["resultat"])


if __name__ == "__main__":
    unittest.main()
