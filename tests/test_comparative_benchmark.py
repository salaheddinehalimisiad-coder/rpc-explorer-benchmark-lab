"""
Tests du script de campagne comparative (Phase 08).

Vérifie :
1. Le proxy TCP de comptage relaie les octets et les compte exactement.
2. Une campagne miniature (serveurs dans le même processus) produit un rapport
   complet, sans erreur, pour les 4 protocoles.
"""

import json
import os
import socket
import tempfile
import threading
import time
import unittest

from benchmark.run_comparative_benchmark import ByteCountingProxy, main


class TestByteCountingProxy(unittest.TestCase):

    def test_counts_bytes_in_both_directions(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)

        def echo_twice():
            conn, _ = server.accept()
            data = conn.recv(1024)
            conn.sendall(data + data)
            conn.close()

        threading.Thread(target=echo_twice, daemon=True).start()
        proxy = ByteCountingProxy("127.0.0.1", server.getsockname()[1])
        try:
            with socket.create_connection(("127.0.0.1", proxy.port)) as client:
                client.sendall(b"hello")
                received = b""
                while len(received) < 10:
                    chunk = client.recv(1024)
                    if not chunk:
                        break
                    received += chunk
            time.sleep(0.1)
            self.assertEqual(received, b"hellohello")
            self.assertEqual(
                proxy.snapshot(),
                {"client_to_server": 5, "server_to_client": 10, "connections": 1},
            )
        finally:
            proxy.close()
            server.close()


class TestComparativeCampaign(unittest.TestCase):

    def test_tiny_in_process_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "results.json")
            rc = main([
                "--in-process", "--iterations", "5", "--warmup", "1",
                "--repetitions", "1", "--concurrency", "1,2", "--per-worker", "3",
                "--wire-calls", "3", "--output", out,
            ])
            self.assertEqual(rc, 0)
            with open(out, encoding="utf-8") as fh:
                report = json.load(fh)

        for key in ("environment", "config", "latency", "concurrency",
                    "wire_bytes", "serialization_microbenchmark"):
            self.assertIn(key, report)

        for operation, by_proto in report["latency"]["pooled"].items():
            self.assertEqual(set(by_proto), {"Local", "Custom RPC", "gRPC", "REST"})
            for proto, res in by_proto.items():
                with self.subTest(operation=operation, proto=proto):
                    self.assertEqual(res["error_count"], 0)
                    self.assertEqual(res["success_count"], 5)

        # gRPC réutilise son canal ; Custom RPC ouvre une connexion par appel.
        fact = report["wire_bytes"]["calculate_factorial"]
        self.assertEqual(fact["gRPC"]["steady_state_per_call"]["tcp_connections_opened"], 0)
        self.assertEqual(fact["Custom RPC"]["steady_state_per_call"]["tcp_connections_opened"], 3)
        self.assertGreater(fact["gRPC"]["steady_state_per_call"]["total_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
