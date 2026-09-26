"""
Tests unitaires et d'intégration pour le moteur de Benchmark (Phase 06).

Vérifie :
1. Précision des calculs statistiques (mean, median, p50, p90, p95, p99, std_dev, RPS)
2. Bon fonctionnement des 4 adaptateurs (Local, Custom RPC, gRPC, REST)
3. Mesure réelle de la taille des payloads (Protobuf vs JSON)
4. Micro-benchmark de sérialisation / désérialisation
5. Mesure de charge concurrente (ThreadPoolExecutor)
6. Suite globale et export des données
"""

import unittest
import json
import statistics

from business.inventory_service import InventoryService
from rpc_core.server_skeleton import RPCServer
from rpc_core.client_stub import RPCClient
from grpc.grpc_server import InventoryGRPCServer
from grpc.grpc_client import InventoryGRPCClient
from rest.rest_server import RestServer
from rest.rest_client import RestClient

from benchmark.metrics import BenchmarkResult
from benchmark.adapters import (
    LocalAdapter,
    CustomRPCAdapter,
    GRPCAdapter,
    RESTAdapter,
)
from benchmark.benchmark_runner import BenchmarkRunner


class TestBenchmarkMetrics(unittest.TestCase):
    """Vérifie l'exactitude des calculs statistiques dans BenchmarkResult."""

    def test_statistical_calculations(self):
        # Échantillon de latences en ms : [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        data = [float(x) for x in range(1, 11)]
        res = BenchmarkResult(
            name="TestMock",
            operation="mock_op",
            latencies_ms=data,
            total_time_seconds=0.1,  # 10 req en 0.1s -> 100 RPS
            warmup_iterations=5,
            error_count=0,
            concurrency=1,
        )

        self.assertEqual(res.min_ms, 1.0)
        self.assertEqual(res.max_ms, 10.0)
        self.assertEqual(res.mean_ms, 5.5)
        self.assertEqual(res.median_ms, 5.5)
        self.assertAlmostEqual(res.std_dev_ms, statistics.stdev(data), places=4)
        self.assertAlmostEqual(res.p50_ms, 5.5, places=2)
        self.assertAlmostEqual(res.p90_ms, 9.1, places=1)
        self.assertAlmostEqual(res.p95_ms, 9.55, places=2)
        self.assertAlmostEqual(res.p99_ms, 9.91, places=2)
        self.assertAlmostEqual(res.throughput_rps, 100.0, places=1)
        self.assertEqual(res.error_rate, 0.0)

    def test_error_rate_calculation(self):
        data = [2.0, 2.5, 3.0]
        res = BenchmarkResult(
            name="TestError",
            operation="mock_op",
            latencies_ms=data,
            total_time_seconds=1.0,
            error_count=1,
        )
        self.assertEqual(res.iterations, 4)
        self.assertEqual(res.error_rate, 25.0)

    def test_to_dict_export(self):
        data = [1.5, 2.5]
        res = BenchmarkResult(
            name="TestExport",
            operation="calc",
            latencies_ms=data,
            total_time_seconds=0.01,
        )
        d = res.to_dict()
        self.assertIn("name", d)
        self.assertIn("latency_ms", d)
        self.assertIn("throughput_rps", d)
        self.assertIn("p95", d["latency_ms"])

        # Vérifier sérialisabilité JSON
        json_output = json.dumps(d)
        self.assertTrue(len(json_output) > 0)

    def test_summary_str(self):
        res = BenchmarkResult("Local", "fact", [1.0, 2.0], 0.005)
        summary = res.summary_str()
        self.assertIn("[Local]", summary)
        self.assertIn("fact", summary)
        self.assertIn("mean:", summary)


class TestBenchmarkAdaptersIntegration(unittest.TestCase):
    """Vérifie le bon fonctionnement des 4 adaptateurs de benchmark."""

    @classmethod
    def setUpClass(cls):
        # 1. Service métier partagé
        cls.service = InventoryService()

        # 2. Serveur Custom RPC sur port dynamique
        cls.custom_rpc_server = RPCServer(host="127.0.0.1", port=0)
        cls.custom_rpc_server.register_method("calculate_factorial", cls.service.calculate_factorial)
        cls.custom_rpc_server.register_method("get_product_details", cls.service.get_product_details)
        cls.custom_rpc_server.register_method("update_stock", cls.service.update_stock)
        cls.custom_rpc_server.register_method("stream_analytics", cls.service.stream_analytics)
        cls.custom_rpc_server.start()
        cls.custom_rpc_client = RPCClient(host="127.0.0.1", port=cls.custom_rpc_server.port)

        # 3. Serveur gRPC sur port dynamique
        cls.grpc_server = InventoryGRPCServer(host="127.0.0.1", port=0, service=cls.service)
        cls.grpc_port = cls.grpc_server.start()
        cls.grpc_client = InventoryGRPCClient(host="127.0.0.1", port=cls.grpc_port)
        cls.grpc_client.connect()

        # 4. Serveur REST sur port dynamique
        cls.rest_server = RestServer(host="127.0.0.1", port=0, service=cls.service)
        cls.rest_port = cls.rest_server.start(threaded=True)
        cls.rest_client = RestClient(base_url=f"http://127.0.0.1:{cls.rest_port}", timeout=5.0)

        # 5. Instanciation des 4 adaptateurs
        cls.adapters = [
            LocalAdapter(service=cls.service),
            CustomRPCAdapter(client=cls.custom_rpc_client),
            GRPCAdapter(client=cls.grpc_client),
            RESTAdapter(client=cls.rest_client),
        ]

    @classmethod
    def tearDownClass(cls):
        for adp in cls.adapters:
            adp.close()
        cls.custom_rpc_server.stop()
        cls.grpc_server.stop(grace=0.1)
        cls.rest_server.stop()

    def test_adapters_uniform_interface(self):
        """Vérifie que les 4 adaptateurs exécutent les mêmes opérations avec succès."""
        for adp in self.adapters:
            with self.subTest(adapter=adp.name):
                # 1. calculate_factorial
                res_fact = adp.call_calculate_factorial(5)
                self.assertEqual(res_fact, 120)

                # 2. get_product_details
                prod = adp.call_get_product_details("PROD-001")
                self.assertEqual(prod["item_id"], "PROD-001")

                # 3. update_stock
                stock_res = adp.call_update_stock("PROD-002", 1)
                self.assertIn("item_id", stock_res)

                # 4. stream_analytics
                events = adp.call_stream_analytics("cpu_usage", 2)
                self.assertEqual(len(list(events)), 2)

    def test_run_latency_benchmark(self):
        """Vérifie l'exécution d'une campagne de latence sur un adaptateur."""
        runner = BenchmarkRunner()
        res = runner.run_latency_benchmark(
            adapter=self.adapters[0],  # Local
            operation="calculate_factorial",
            iterations=20,
            warmup_iterations=5,
            n=5,
        )
        self.assertEqual(res.name, "Local")
        self.assertEqual(res.operation, "calculate_factorial")
        self.assertEqual(len(res.latencies_ms), 20)
        self.assertGreater(res.throughput_rps, 0.0)

    def test_run_concurrency_benchmark(self):
        """Vérifie l'exécution sous charge concurrente."""
        runner = BenchmarkRunner()
        conc_results = runner.run_concurrency_benchmark(
            adapter=self.adapters[0],
            operation="calculate_factorial",
            concurrency_levels=[1, 2],
            iterations_per_worker=10,
            n=5,
        )
        self.assertIn(1, conc_results)
        self.assertIn(2, conc_results)
        self.assertEqual(conc_results[2].iterations, 20)

    def test_run_full_suite(self):
        """Vérifie l'exécution complète du benchmark multi-protocoles."""
        runner = BenchmarkRunner(adapters=self.adapters)
        full_report = runner.run_full_suite(iterations=15, warmup_iterations=3)

        self.assertIn("latency_comparison", full_report)
        self.assertIn("payload_sizes", full_report)
        self.assertIn("serialization_microbenchmark", full_report)

        # Vérifier que les 4 adaptateurs sont présents dans le comparatif de latence
        self.assertIn("Local", full_report["latency_comparison"])
        self.assertIn("Custom RPC", full_report["latency_comparison"])
        self.assertIn("gRPC", full_report["latency_comparison"])
        self.assertIn("REST", full_report["latency_comparison"])


class TestBenchmarkPayloadAndSerialization(unittest.TestCase):
    """Vérifie les mesures de taille de payload et de micro-benchmark de sérialisation."""

    def setUp(self):
        self.runner = BenchmarkRunner()

    def test_payload_size_comparison(self):
        payloads = self.runner.run_payload_size_comparison()

        self.assertIn("calculate_factorial", payloads)
        self.assertIn("get_product_details", payloads)
        self.assertIn("compactness_gain_percent", payloads)

        # Vérifier que Protobuf est réellement plus compact que JSON Custom RPC
        fact_grpc = payloads["calculate_factorial"]["gRPC"]["total_bytes"]
        fact_custom = payloads["calculate_factorial"]["Custom RPC"]["total_bytes"]
        self.assertLess(fact_grpc, fact_custom)

        prod_grpc = payloads["get_product_details"]["gRPC"]["total_bytes"]
        prod_custom = payloads["get_product_details"]["Custom RPC"]["total_bytes"]
        self.assertLess(prod_grpc, prod_custom)

    def test_serialization_microbenchmark(self):
        ser_res = self.runner.run_serialization_benchmark(iterations=100)
        self.assertIn("json", ser_res)
        self.assertIn("protobuf", ser_res)
        self.assertGreater(ser_res["json"]["total_us"], 0.0)
        self.assertGreater(ser_res["protobuf"]["total_us"], 0.0)

    def test_format_comparison_table(self):
        r1 = BenchmarkResult("Local", "calculate_factorial", [0.01, 0.02], 0.001)
        r2 = BenchmarkResult("gRPC", "calculate_factorial", [1.2, 1.5], 0.003)
        table = BenchmarkRunner.format_comparison_table([r1, r2])
        self.assertIn("Protocole", table)
        self.assertIn("Local", table)
        self.assertIn("gRPC", table)


if __name__ == "__main__":
    unittest.main()
