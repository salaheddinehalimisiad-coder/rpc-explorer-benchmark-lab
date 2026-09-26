"""
Tests unitaires et d'intégration réseau pour l'API REST HTTP/JSON (Phase 05)

Vérifie :
1. Routes et codes de statut HTTP de l'application Flask (test_client)
2. Gestion des erreurs et validation des entrées (400, 404, 409, 405)
3. Intégration Client -> Serveur réseau réelle de bout en bout sur port dynamique
4. Thread-safety et concurrence des requêtes HTTP
5. Cycle de vie du serveur et context manager
"""

import unittest
import threading
from concurrent.futures import ThreadPoolExecutor

from business.inventory_service import InventoryService
from rest.rest_server import create_app, RestServer
from rest.rest_client import RestClient, RestClientError


class TestFlaskEndpointsUnit(unittest.TestCase):
    """Vérifie unitairement les routes Flask via app.test_client()."""

    def setUp(self):
        self.service = InventoryService()
        self.app = create_app(self.service)
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "inventory_rest")

    def test_calculate_factorial_success(self):
        resp = self.client.post("/api/factorial", json={"n": 5})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["n"], 5)
        self.assertEqual(data["result"], 120)
        self.assertIn("execution_time_ms", data)
        self.assertGreaterEqual(data["execution_time_ms"], 0.0)

    def test_calculate_factorial_boundaries(self):
        resp0 = self.client.post("/api/factorial", json={"n": 0})
        self.assertEqual(resp0.status_code, 200)
        self.assertEqual(resp0.get_json()["result"], 1)

        resp1 = self.client.post("/api/factorial", json={"n": 1})
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.get_json()["result"], 1)

        resp10 = self.client.post("/api/factorial", json={"n": 10})
        self.assertEqual(resp10.status_code, 200)
        self.assertEqual(resp10.get_json()["result"], 3628800)

    def test_calculate_factorial_missing_param(self):
        resp = self.client.post("/api/factorial", json={})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["code"], "INVALID_ARGUMENT")

    def test_calculate_factorial_invalid_types(self):
        # Booléen
        resp_bool = self.client.post("/api/factorial", json={"n": True})
        self.assertEqual(resp_bool.status_code, 400)

        # Chaîne
        resp_str = self.client.post("/api/factorial", json={"n": "cinq"})
        self.assertEqual(resp_str.status_code, 400)

    def test_calculate_factorial_out_of_bounds(self):
        # Négatif
        resp_neg = self.client.post("/api/factorial", json={"n": -5})
        self.assertEqual(resp_neg.status_code, 400)

        # > 200
        resp_large = self.client.post("/api/factorial", json={"n": 201})
        self.assertEqual(resp_large.status_code, 400)

    def test_get_product_details_success(self):
        resp = self.client.get("/api/products/PROD-001")
        self.assertEqual(resp.status_code, 200)
        prod = resp.get_json()
        self.assertEqual(prod["item_id"], "PROD-001")
        self.assertEqual(prod["name"], "Laptop ProBook 450")
        self.assertEqual(prod["stock"], 42)
        self.assertEqual(prod["price"], 1299.99)
        self.assertEqual(prod["category"], "Electronics")

    def test_get_product_details_not_found(self):
        resp = self.client.get("/api/products/PROD-UNKNOWN")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data["code"], "NOT_FOUND")

    def test_update_stock_success(self):
        # Initial: PROD-002 a stock=150
        resp = self.client.post(
            "/api/products/PROD-002/stock", json={"quantity_delta": 10}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["item_id"], "PROD-002")
        self.assertEqual(data["new_stock"], 160)

    def test_update_stock_not_found(self):
        resp = self.client.post(
            "/api/products/PROD-NOT-EXIST/stock", json={"quantity_delta": 5}
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data["code"], "NOT_FOUND")

    def test_update_stock_insufficient(self):
        # PROD-003 a stock=500
        resp = self.client.post(
            "/api/products/PROD-003/stock", json={"quantity_delta": -1000}
        )
        self.assertEqual(resp.status_code, 409)
        data = resp.get_json()
        self.assertEqual(data["code"], "INSUFFICIENT_STOCK")

    def test_update_stock_invalid_body(self):
        resp = self.client.post("/api/products/PROD-001/stock", json={})
        self.assertEqual(resp.status_code, 400)

    def test_stream_analytics_success(self):
        resp = self.client.get("/api/analytics/cpu_usage?count=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["metric"], "cpu_usage")
        self.assertEqual(data["count"], 5)
        self.assertEqual(len(data["events"]), 5)

    def test_stream_analytics_all_supported_metrics(self):
        for metric in ["cpu_usage", "memory_usage", "request_rate", "error_rate"]:
            resp = self.client.get(f"/api/analytics/{metric}?count=3")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["metric"], metric)

    def test_stream_analytics_invalid_metric(self):
        resp = self.client.get("/api/analytics/non_supported_metric")
        self.assertEqual(resp.status_code, 400)

    def test_stream_analytics_invalid_count(self):
        resp = self.client.get("/api/analytics/cpu_usage?count=0")
        self.assertEqual(resp.status_code, 400)

        resp2 = self.client.get("/api/analytics/cpu_usage?count=abc")
        self.assertEqual(resp2.status_code, 400)

    def test_method_not_allowed(self):
        resp = self.client.get("/api/factorial")
        self.assertEqual(resp.status_code, 405)
        data = resp.get_json()
        self.assertEqual(data["code"], "METHOD_NOT_ALLOWED")


class TestRestNetworkIntegration(unittest.TestCase):
    """Tests d'intégration réels Client -> Serveur HTTP via socket TCP/HTTP."""

    @classmethod
    def setUpClass(cls):
        cls.service = InventoryService()
        cls.server = RestServer(host="127.0.0.1", port=0, service=cls.service)
        cls.port = cls.server.start(threaded=True)
        cls.client = RestClient(base_url=f"http://127.0.0.1:{cls.port}", timeout=5.0)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.server.stop()

    def test_health_check(self):
        data = self.client.health()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "inventory_rest")

    def test_calculate_factorial(self):
        res = self.client.calculate_factorial(6)
        self.assertEqual(res, 720)

    def test_calculate_factorial_with_metadata(self):
        data = self.client.calculate_factorial_with_metadata(5)
        self.assertEqual(data["result"], 120)
        self.assertIn("execution_time_ms", data)
        self.assertGreaterEqual(data["execution_time_ms"], 0.0)

    def test_calculate_factorial_error_handling(self):
        with self.assertRaises(RestClientError) as cm:
            self.client.calculate_factorial(-3)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.error_code, "INVALID_ARGUMENT")

    def test_get_product_details(self):
        prod = self.client.get_product_details("PROD-001")
        self.assertEqual(prod["item_id"], "PROD-001")
        self.assertEqual(prod["name"], "Laptop ProBook 450")
        self.assertEqual(prod["stock"], 42)

    def test_get_product_details_not_found(self):
        with self.assertRaises(RestClientError) as cm:
            self.client.get_product_details("PROD-NONEXISTENT")
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.error_code, "NOT_FOUND")

    def test_update_stock_success(self):
        # PROD-004 stock initial : 75
        res = self.client.update_stock("PROD-004", 15)
        self.assertEqual(res["new_stock"], 90)

        # Vérifier mise à jour réelle
        details = self.client.get_product_details("PROD-004")
        self.assertEqual(details["stock"], 90)

    def test_update_stock_insufficient(self):
        with self.assertRaises(RestClientError) as cm:
            self.client.update_stock("PROD-004", -500)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertEqual(cm.exception.error_code, "INSUFFICIENT_STOCK")

    def test_stream_analytics(self):
        events = self.client.stream_analytics("cpu_usage", count=4)
        self.assertEqual(len(events), 4)
        for ev in events:
            self.assertEqual(ev["metric"], "cpu_usage")
            self.assertIn("value", ev)
            self.assertIn("timestamp", ev)

    def test_context_manager_server_and_client(self):
        """Vérifie le cycle de vie propre avec context managers."""
        with RestServer(port=0) as temp_srv:
            self.assertTrue(temp_srv.is_running)
            with RestClient(base_url=f"http://127.0.0.1:{temp_srv.bound_port}") as temp_cli:
                res = temp_cli.calculate_factorial(4)
                self.assertEqual(res, 24)

    def test_concurrent_requests(self):
        """Vérifie la robustesse face à des requêtes HTTP concurrentes."""
        def worker(idx):
            return self.client.calculate_factorial(5)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(20)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 20)
        self.assertTrue(all(r == 120 for r in results))


if __name__ == "__main__":
    unittest.main()
