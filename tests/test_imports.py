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

        # Vérifie que les méthodes sont bien des placeholders déclarés
        client = RPCClient()
        with self.assertRaises(NotImplementedError):
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

        with self.assertRaises(NotImplementedError):
            service.calculate_factorial(5)

        with self.assertRaises(NotImplementedError):
            service.get_product_details("PROD-001")

        with self.assertRaises(NotImplementedError):
            service.update_stock("PROD-001", 10)

    def test_grpc_layer_imports(self):
        """Vérifie l'importation des squelettes gRPC."""
        from grpc.grpc_server import InventoryGRPCServer
        from grpc.grpc_client import InventoryGRPCClient

        server = InventoryGRPCServer()
        client = InventoryGRPCClient()

        self.assertTrue(hasattr(server, "start"))
        self.assertTrue(hasattr(client, "calculate_factorial"))

        with self.assertRaises(NotImplementedError):
            server.start()

        with self.assertRaises(NotImplementedError):
            client.calculate_factorial(5)

    def test_rest_layer_imports(self):
        """Vérifie l'importation des squelettes REST."""
        from rest.rest_server import RestServer
        from rest.rest_client import RestClient

        server = RestServer()
        client = RestClient()

        self.assertTrue(hasattr(server, "start"))
        self.assertTrue(hasattr(client, "calculate_factorial"))

        with self.assertRaises(NotImplementedError):
            server.start()

        with self.assertRaises(NotImplementedError):
            client.calculate_factorial(5)

    def test_benchmark_layer_imports(self):
        """Vérifie l'importation du banc d'essai comparatif."""
        from benchmark import BenchmarkRunner
        from benchmark.adapters import BaseBenchmarkAdapter

        runner = BenchmarkRunner()
        self.assertTrue(hasattr(runner, "run_latency_benchmark"))
        self.assertTrue(hasattr(runner, "run_payload_size_comparison"))

        with self.assertRaises(NotImplementedError):
            runner.run_payload_size_comparison()

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
