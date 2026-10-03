"""
Tests d'intégration et unitaires pour l'implémentation gRPC / Protobuf (Phase 04)

Vérifie :
1. Intégrité et sérialisation binaire des messages Protobuf
2. Logique du Servicer et mapping des erreurs vers les StatusCode gRPC
3. Intégration Client -> Serveur de bout en bout sur port dynamique
4. Appels unaires et Server Streaming en flux continu
5. Gestion du cycle de vie du serveur et fermeture propre
"""

import unittest
import json
from unittest.mock import MagicMock

import grpc

from business.inventory_service import InventoryService
from protos import inventory_pb2
from protos import inventory_pb2_grpc
from grpc_impl.grpc_server import InventoryServicer, InventoryGRPCServer
from grpc_impl.grpc_client import InventoryGRPCClient


class MockServicerContext:
    """Mock léger pour tester unitairement les méthodes du servicer gRPC."""

    def __init__(self):
        self.code = None
        self.details = None
        self.aborted = False
        self._active = True

    def abort(self, code, details):
        self.code = code
        self.details = details
        self.aborted = True
        raise grpc.RpcError(f"Abort called: {code} - {details}")

    def is_active(self):
        return self._active


class TestProtobufMessages(unittest.TestCase):
    """Vérifie la sérialisation, désérialisation et compacité des messages Protobuf."""

    def test_factorial_messages(self):
        req = inventory_pb2.FactorialRequest(n=10)
        serialized = req.SerializeToString()
        deserialized = inventory_pb2.FactorialRequest()
        deserialized.ParseFromString(serialized)
        self.assertEqual(deserialized.n, 10)

        resp = inventory_pb2.FactorialResponse(result=3628800, execution_time_ms=0.125)
        serialized_resp = resp.SerializeToString()
        deserialized_resp = inventory_pb2.FactorialResponse()
        deserialized_resp.ParseFromString(serialized_resp)
        self.assertEqual(deserialized_resp.result, 3628800)
        self.assertAlmostEqual(deserialized_resp.execution_time_ms, 0.125, places=3)

    def test_product_messages(self):
        req = inventory_pb2.ProductRequest(item_id="PROD-001")
        data = req.SerializeToString()
        req2 = inventory_pb2.ProductRequest.FromString(data)
        self.assertEqual(req2.item_id, "PROD-001")

        resp = inventory_pb2.ProductResponse(
            item_id="PROD-001",
            name="Laptop Dell XPS 15",
            quantity=15,
            unit_price=1499.99,
            category="Électronique",
            success=True,
            message="Produit trouvé.",
        )
        data_resp = resp.SerializeToString()
        resp2 = inventory_pb2.ProductResponse.FromString(data_resp)
        self.assertEqual(resp2.name, "Laptop Dell XPS 15")
        self.assertEqual(resp2.quantity, 15)
        self.assertAlmostEqual(resp2.unit_price, 1499.99, places=2)
        self.assertTrue(resp2.success)

    def test_update_stock_request(self):
        req = inventory_pb2.UpdateStockRequest(item_id="PROD-002", quantity_delta=-3)
        data = req.SerializeToString()
        req2 = inventory_pb2.UpdateStockRequest.FromString(data)
        self.assertEqual(req2.item_id, "PROD-002")
        self.assertEqual(req2.quantity_delta, -3)

    def test_analytics_messages(self):
        req = inventory_pb2.AnalyticsRequest(metric_name="cpu_usage", count=5)
        data = req.SerializeToString()
        req2 = inventory_pb2.AnalyticsRequest.FromString(data)
        self.assertEqual(req2.metric_name, "cpu_usage")
        self.assertEqual(req2.count, 5)

        resp = inventory_pb2.AnalyticsResponse(
            metric_name="cpu_usage",
            value=45.2,
            timestamp=1700000000000,
            server_id="server_alpha",
        )
        data_resp = resp.SerializeToString()
        resp2 = inventory_pb2.AnalyticsResponse.FromString(data_resp)
        self.assertEqual(resp2.metric_name, "cpu_usage")
        self.assertAlmostEqual(resp2.value, 45.2, places=1)
        self.assertEqual(resp2.timestamp, 1700000000000)
        self.assertEqual(resp2.server_id, "server_alpha")

    def test_protobuf_payload_is_more_compact_than_json(self):
        """Démontre que le payload binaire Protobuf est plus compact que JSON."""
        resp = inventory_pb2.ProductResponse(
            item_id="PROD-001",
            name="Laptop Dell XPS 15",
            quantity=15,
            unit_price=1499.99,
            category="Électronique",
            success=True,
            message="Produit trouvé.",
        )
        protobuf_bytes = resp.SerializeToString()

        json_dict = {
            "item_id": "PROD-001",
            "name": "Laptop Dell XPS 15",
            "quantity": 15,
            "unit_price": 1499.99,
            "category": "Électronique",
            "success": True,
            "message": "Produit trouvé.",
        }
        json_bytes = json.dumps(json_dict).encode("utf-8")

        self.assertLess(len(protobuf_bytes), len(json_bytes))


class TestInventoryServicerUnit(unittest.TestCase):
    """Vérifie unitairement les conversions et codes d'erreurs du servicer gRPC."""

    def setUp(self):
        self.servicer = InventoryServicer(InventoryService())

    def test_calculate_factorial_success(self):
        ctx = MockServicerContext()
        req = inventory_pb2.FactorialRequest(n=5)
        resp = self.servicer.CalculateFactorial(req, ctx)
        self.assertEqual(resp.result, 120)
        self.assertGreaterEqual(resp.execution_time_ms, 0.0)

    def test_calculate_factorial_negative(self):
        ctx = MockServicerContext()
        req = inventory_pb2.FactorialRequest(n=-1)
        with self.assertRaises(grpc.RpcError):
            self.servicer.CalculateFactorial(req, ctx)
        self.assertEqual(ctx.code, grpc.StatusCode.INVALID_ARGUMENT)

    def test_calculate_factorial_int64_overflow(self):
        ctx = MockServicerContext()
        req = inventory_pb2.FactorialRequest(n=25)
        with self.assertRaises(grpc.RpcError):
            self.servicer.CalculateFactorial(req, ctx)
        self.assertEqual(ctx.code, grpc.StatusCode.INVALID_ARGUMENT)
        self.assertIn("dépasse la capacité", ctx.details)

    def test_get_product_details_success(self):
        ctx = MockServicerContext()
        req = inventory_pb2.ProductRequest(item_id="PROD-001")
        resp = self.servicer.GetProductDetails(req, ctx)
        self.assertEqual(resp.item_id, "PROD-001")
        self.assertTrue(resp.success)

    def test_get_product_details_not_found(self):
        ctx = MockServicerContext()
        req = inventory_pb2.ProductRequest(item_id="PROD-INCONNU")
        with self.assertRaises(grpc.RpcError):
            self.servicer.GetProductDetails(req, ctx)
        self.assertEqual(ctx.code, grpc.StatusCode.NOT_FOUND)

    def test_get_product_details_empty_id(self):
        ctx = MockServicerContext()
        req = inventory_pb2.ProductRequest(item_id="")
        with self.assertRaises(grpc.RpcError):
            self.servicer.GetProductDetails(req, ctx)
        self.assertEqual(ctx.code, grpc.StatusCode.INVALID_ARGUMENT)

    def test_update_stock_success(self):
        ctx = MockServicerContext()
        req = inventory_pb2.UpdateStockRequest(item_id="PROD-003", quantity_delta=5)
        resp = self.servicer.UpdateStock(req, ctx)
        self.assertEqual(resp.item_id, "PROD-003")
        self.assertEqual(resp.quantity, 505)  # 500 + 5
        self.assertTrue(resp.success)

    def test_update_stock_not_found(self):
        ctx = MockServicerContext()
        req = inventory_pb2.UpdateStockRequest(item_id="PROD-999", quantity_delta=1)
        with self.assertRaises(grpc.RpcError):
            self.servicer.UpdateStock(req, ctx)
        self.assertEqual(ctx.code, grpc.StatusCode.NOT_FOUND)

    def test_update_stock_insufficient_stock(self):
        ctx = MockServicerContext()
        req = inventory_pb2.UpdateStockRequest(item_id="PROD-003", quantity_delta=-1000)
        with self.assertRaises(grpc.RpcError):
            self.servicer.UpdateStock(req, ctx)
        self.assertEqual(ctx.code, grpc.StatusCode.FAILED_PRECONDITION)

    def test_stream_analytics_success(self):
        ctx = MockServicerContext()
        req = inventory_pb2.AnalyticsRequest(metric_name="cpu_usage", count=3)
        events = list(self.servicer.StreamAnalytics(req, ctx))
        self.assertEqual(len(events), 3)
        for ev in events:
            self.assertEqual(ev.metric_name, "cpu_usage")
            self.assertIsInstance(ev.value, float)
            self.assertGreater(ev.timestamp, 0)

    def test_stream_analytics_invalid_metric(self):
        ctx = MockServicerContext()
        req = inventory_pb2.AnalyticsRequest(metric_name="non_existent", count=3)
        with self.assertRaises(grpc.RpcError):
            list(self.servicer.StreamAnalytics(req, ctx))
        self.assertEqual(ctx.code, grpc.StatusCode.INVALID_ARGUMENT)

    def test_stream_analytics_invalid_count(self):
        ctx = MockServicerContext()
        req = inventory_pb2.AnalyticsRequest(metric_name="cpu_usage", count=0)
        with self.assertRaises(grpc.RpcError):
            list(self.servicer.StreamAnalytics(req, ctx))
        self.assertEqual(ctx.code, grpc.StatusCode.INVALID_ARGUMENT)


class TestInventoryGRPCIntegration(unittest.TestCase):
    """Tests d'intégration réels Client -> Serveur via socket réseau et HTTP/2."""

    @classmethod
    def setUpClass(cls):
        # Utiliser un service dédié avec inventaire frais
        cls.service = InventoryService()
        cls.server = InventoryGRPCServer(host="127.0.0.1", port=0, service=cls.service)
        cls.port = cls.server.start()
        cls.client = InventoryGRPCClient(host="127.0.0.1", port=cls.port)
        cls.client.connect()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.server.stop(grace=0.2)

    def test_calculate_factorial_values(self):
        self.assertEqual(self.client.calculate_factorial(0), 1)
        self.assertEqual(self.client.calculate_factorial(1), 1)
        self.assertEqual(self.client.calculate_factorial(5), 120)
        self.assertEqual(self.client.calculate_factorial(10), 3628800)
        self.assertEqual(self.client.calculate_factorial(20), 2432902008176640000)

    def test_calculate_factorial_with_metadata(self):
        data = self.client.calculate_factorial_with_metadata(6)
        self.assertEqual(data["result"], 720)
        self.assertIn("execution_time_ms", data)
        self.assertGreaterEqual(data["execution_time_ms"], 0.0)

    def test_calculate_factorial_overflow_int64_error(self):
        with self.assertRaises(grpc.RpcError) as cm:
            self.client.calculate_factorial(21)
        self.assertEqual(cm.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)
        self.assertIn("int64", cm.exception.details())

    def test_calculate_factorial_negative_error(self):
        with self.assertRaises(grpc.RpcError) as cm:
            self.client.calculate_factorial(-3)
        self.assertEqual(cm.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_get_product_details_success(self):
        prod = self.client.get_product_details("PROD-001")
        self.assertEqual(prod["item_id"], "PROD-001")
        self.assertEqual(prod["name"], "Laptop ProBook 450")
        self.assertEqual(prod["quantity"], 42)
        self.assertAlmostEqual(prod["unit_price"], 1299.99, places=2)
        self.assertEqual(prod["category"], "Electronics")
        self.assertTrue(prod["success"])

    def test_get_product_details_not_found(self):
        with self.assertRaises(grpc.RpcError) as cm:
            self.client.get_product_details("PROD-NOT-EXIST")
        self.assertEqual(cm.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_update_stock_success(self):
        # PROD-002 stock initial: 150
        res1 = self.client.update_stock("PROD-002", 5)
        self.assertEqual(res1["new_stock"], 155)
        self.assertTrue(res1["success"])

        # Vérifier répercussion via get_product_details
        details = self.client.get_product_details("PROD-002")
        self.assertEqual(details["quantity"], 155)

    def test_update_stock_insufficient(self):
        with self.assertRaises(grpc.RpcError) as cm:
            self.client.update_stock("PROD-002", -1000)
        self.assertEqual(cm.exception.code(), grpc.StatusCode.FAILED_PRECONDITION)

    def test_update_stock_not_found(self):
        with self.assertRaises(grpc.RpcError) as cm:
            self.client.update_stock("PROD-UNKNOWN", 10)
        self.assertEqual(cm.exception.code(), grpc.StatusCode.NOT_FOUND)

    def test_stream_analytics_server_streaming(self):
        events = list(self.client.stream_analytics("cpu_usage", count=4))
        self.assertEqual(len(events), 4)
        for ev in events:
            self.assertEqual(ev["metric_name"], "cpu_usage")
            self.assertIsInstance(ev["value"], float)
            self.assertIsInstance(ev["timestamp"], int)
            self.assertTrue(ev["server_id"].startswith("grpc_server"))

    def test_stream_analytics_all_metrics(self):
        for metric in ["cpu_usage", "memory_usage", "request_rate", "error_rate"]:
            events = list(self.client.stream_analytics(metric, count=2))
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["metric_name"], metric)

    def test_stream_analytics_invalid_metric(self):
        with self.assertRaises(grpc.RpcError) as cm:
            list(self.client.stream_analytics("unknown_metric", count=3))
        self.assertEqual(cm.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)

    def test_context_manager_server_and_client(self):
        """Vérifie le fonctionnement sous bloc with des context managers."""
        with InventoryGRPCServer(port=0) as temp_server:
            self.assertTrue(temp_server.is_running)
            with InventoryGRPCClient(port=temp_server.bound_port) as temp_client:
                res = temp_client.calculate_factorial(4)
                self.assertEqual(res, 24)


if __name__ == "__main__":
    unittest.main()
