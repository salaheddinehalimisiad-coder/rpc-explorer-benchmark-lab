"""
Tests d'importation et de cohérence des interfaces (Phase 01 - Fondation)

Vérifie :
1. Que tous les modules créés s'importent sans erreur
2. Que les classes et composants fondamentaux sont présents
3. Que les méthodes placeholders lèvent bien NotImplementedError (règle de non-faux-code)
"""

import unittest


class TestImportsAndInterfaces(unittest.TestCase):
    """Vérifie la cohérence des imports et des interfaces."""

    def test_rpc_core_imports(self):
        """Vérifie l'importation du cœur RPC Custom."""
        from rpc_core import serializer, client_stub, server_skeleton
        from rpc_core.serializer import RPCSerializer
        from rpc_core.client_stub import RPCClient, RPCError
        from rpc_core.server_skeleton import RPCServer, RPCMethodNotFoundError

        self.assertTrue(hasattr(RPCSerializer, "serialize_request"))
        self.assertTrue(hasattr(RPCSerializer, "deserialize_request"))
        self.assertTrue(hasattr(RPCClient, "call"))
        self.assertTrue(hasattr(RPCServer, "register_method"))
        self.assertTrue(hasattr(RPCServer, "start"))

        # En Phase 02, RPCClient est pleinement implémenté et lève ConnectionError si aucun serveur n'écoute
        client = RPCClient()
        with self.assertRaises(ConnectionError):
            client.call("test_method")

    def test_business_layer_imports(self):
        """Vérifie l'importation de la couche métier indépendante."""
        from business import InventoryService
        from business.inventory_service import InventoryService as DirectInventoryService

        self.assertIs(InventoryService, DirectInventoryService)

        service = InventoryService()
        self.assertTrue(hasattr(service, "calculate_factorial"))
        self.assertTrue(hasattr(service, "get_product_details"))
        self.assertTrue(hasattr(service, "update_stock"))
        self.assertTrue(hasattr(service, "stream_analytics"))

        # Phase 03 : les méthodes sont maintenant implémentées
        self.assertEqual(service.calculate_factorial(5), 120)

        details = service.get_product_details("PROD-001")
        self.assertEqual(details["item_id"], "PROD-001")

        result = service.update_stock("PROD-001", 1)
        self.assertIn("new_stock", result)

    def test_grpc_layer_imports(self):
        """Vérifie l'importation et l'interface des composants gRPC."""
        from grpc.grpc_server import InventoryGRPCServer, InventoryServicer
        from grpc.grpc_client import InventoryGRPCClient
        import grpc

        server = InventoryGRPCServer(port=0)
        client = InventoryGRPCClient(port=59999, timeout=0.5)

        self.assertTrue(hasattr(server, "start"))
        self.assertTrue(hasattr(server, "stop"))
        self.assertTrue(hasattr(server, "servicer"))
        self.assertIsInstance(server.servicer, InventoryServicer)

        self.assertTrue(hasattr(client, "calculate_factorial"))
        self.assertTrue(hasattr(client, "get_product_details"))
        self.assertTrue(hasattr(client, "update_stock"))
        self.assertTrue(hasattr(client, "stream_analytics"))
        self.assertTrue(hasattr(client, "close"))

        # En Phase 04, l'appel sans serveur actif lève une erreur gRPC (canal indisponible)
        with self.assertRaises(grpc.RpcError):
            client.calculate_factorial(5)
        client.close()

    def test_rest_layer_imports(self):
        """Vérifie l'importation et l'interface des composants REST."""
        from rest.rest_server import RestServer, create_app
        from rest.rest_client import RestClient, RestClientError

        server = RestServer(port=0)
        client = RestClient(base_url="http://127.0.0.1:59998", timeout=0.5)

        self.assertTrue(hasattr(server, "start"))
        self.assertTrue(hasattr(server, "stop"))
        self.assertTrue(hasattr(server, "app"))

        self.assertTrue(hasattr(client, "calculate_factorial"))
        self.assertTrue(hasattr(client, "get_product_details"))
        self.assertTrue(hasattr(client, "update_stock"))
        self.assertTrue(hasattr(client, "stream_analytics"))
        self.assertTrue(hasattr(client, "health"))
        self.assertTrue(hasattr(client, "close"))

        # En Phase 05, l'appel sans serveur actif lève RestClientError
        with self.assertRaises(RestClientError):
            client.calculate_factorial(5)
        client.close()

    def test_benchmark_layer_imports(self):
        """Vérifie l'importation et l'interface du banc d'essai comparatif."""
        from benchmark import (
            BenchmarkRunner,
            BenchmarkResult,
            BaseBenchmarkAdapter,
            LocalAdapter,
            CustomRPCAdapter,
            GRPCAdapter,
            RESTAdapter,
        )

        runner = BenchmarkRunner()
        self.assertTrue(hasattr(runner, "run_latency_benchmark"))
        self.assertTrue(hasattr(runner, "run_payload_size_comparison"))
        self.assertTrue(hasattr(runner, "run_serialization_benchmark"))
        self.assertTrue(hasattr(runner, "run_concurrency_benchmark"))
        self.assertTrue(hasattr(runner, "run_full_suite"))

        # En Phase 06, run_payload_size_comparison() est pleinement implémenté
        payloads = runner.run_payload_size_comparison()
        self.assertIn("calculate_factorial", payloads)
        self.assertIn("get_product_details", payloads)

    def test_failure_simulator_imports(self):
        """Vérifie l'importation du simulateur de pannes."""
        from failure_simulator import FailureSimulator

        sim = FailureSimulator()
        self.assertTrue(hasattr(sim, "enable_latency_spike"))
        self.assertTrue(hasattr(sim, "simulate_server_down"))
        self.assertTrue(hasattr(sim, "simulate_contract_breaking_change"))

        with self.assertRaises(NotImplementedError):
            sim.enable_latency_spike()

    def test_under_the_hood_imports(self):
        """Vérifie l'importation du module de traçabilité pédagogique."""
        from under_the_hood import RPCTracer

        tracer = RPCTracer()
        self.assertTrue(hasattr(tracer, "record_step"))
        self.assertTrue(hasattr(tracer, "display_trace"))

        with self.assertRaises(NotImplementedError):
            tracer.display_trace()

    def test_cli_imports(self):
        """Vérifie l'importation du CLI Runner."""
        from cli import CLIRunner

        cli = CLIRunner()
        self.assertTrue(hasattr(cli, "run_interactive_menu"))
        self.assertTrue(hasattr(cli, "run_benchmark_mode"))

        with self.assertRaises(NotImplementedError):
            cli.run_interactive_menu()


if __name__ == "__main__":
    unittest.main()
