"""
Suite de tests pour le Service Métier InventoryService (Phase 03)

Couvre :
1. calculate_factorial — nominal + validations
2. get_product_details — nominal + validations
3. update_stock — nominal + validations + thread-safety
4. stream_analytics — nominal + validations + structure
5. Intégration RPC de bout en bout :
   RPCClient → TCP → RPCServer → InventoryService
"""

import time
import unittest
import threading
from business.inventory_service import InventoryService, DEMO_CATALOG, SUPPORTED_METRICS
from rpc_core.client_stub import RPCClient, RPCError
from rpc_core.server_skeleton import RPCServer


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Tests unitaires : calculate_factorial
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateFactorial(unittest.TestCase):
    """Tests unitaires pour calculate_factorial."""

    def setUp(self):
        self.service = InventoryService()

    def test_factorial_zero(self):
        """0! = 1."""
        self.assertEqual(self.service.calculate_factorial(0), 1)

    def test_factorial_one(self):
        """1! = 1."""
        self.assertEqual(self.service.calculate_factorial(1), 1)

    def test_factorial_five(self):
        """5! = 120."""
        self.assertEqual(self.service.calculate_factorial(5), 120)

    def test_factorial_ten(self):
        """10! = 3628800."""
        self.assertEqual(self.service.calculate_factorial(10), 3628800)

    def test_factorial_twenty(self):
        """20! = 2432902008176640000."""
        self.assertEqual(self.service.calculate_factorial(20), 2432902008176640000)

    def test_factorial_boundary_200(self):
        """200 est la limite haute — doit réussir sans exception."""
        result = self.service.calculate_factorial(200)
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_factorial_negative_raises(self):
        """n < 0 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.calculate_factorial(-1)
        self.assertIn("positif ou nul", str(ctx.exception))

    def test_factorial_exceeds_limit_raises(self):
        """n > 200 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.calculate_factorial(201)
        self.assertIn("200", str(ctx.exception))

    def test_factorial_float_raises(self):
        """n = float → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.calculate_factorial(5.0)  # type: ignore
        self.assertIn("entier", str(ctx.exception))

    def test_factorial_string_raises(self):
        """n = str → ValueError."""
        with self.assertRaises(ValueError):
            self.service.calculate_factorial("5")  # type: ignore

    def test_factorial_bool_raises(self):
        """n = bool → ValueError (bool est un sous-type de int en Python)."""
        with self.assertRaises(ValueError):
            self.service.calculate_factorial(True)  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Tests unitaires : get_product_details
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetProductDetails(unittest.TestCase):
    """Tests unitaires pour get_product_details."""

    def setUp(self):
        self.service = InventoryService()

    def test_get_existing_product(self):
        """Récupérer un produit existant retourne ses détails complets."""
        result = self.service.get_product_details("PROD-001")
        self.assertEqual(result["item_id"], "PROD-001")
        self.assertEqual(result["name"], "Laptop ProBook 450")
        self.assertEqual(result["category"], "Electronics")
        self.assertEqual(result["price"], 1299.99)
        self.assertEqual(result["stock"], 42)
        self.assertEqual(result["unit"], "unit")
        self.assertIn("last_updated", result)

    def test_get_product_contains_timestamp(self):
        """Le champ last_updated est un timestamp ISO 8601 UTC."""
        result = self.service.get_product_details("PROD-002")
        ts = result["last_updated"]
        self.assertIsInstance(ts, str)
        self.assertIn("T", ts)
        # Doit contenir un indicateur UTC (+00:00 ou Z)
        self.assertTrue(ts.endswith("+00:00") or ts.endswith("Z"), f"Timestamp non-UTC : {ts}")

    def test_get_all_demo_products(self):
        """Tous les produits du catalogue de démonstration sont accessibles."""
        for item_id in DEMO_CATALOG:
            result = self.service.get_product_details(item_id)
            self.assertEqual(result["item_id"], item_id)

    def test_unknown_product_raises(self):
        """Produit inconnu → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.get_product_details("INEXISTANT-999")
        self.assertIn("introuvable", str(ctx.exception))

    def test_empty_item_id_raises(self):
        """item_id vide → ValueError."""
        with self.assertRaises(ValueError):
            self.service.get_product_details("")

    def test_non_string_item_id_raises(self):
        """item_id non-string → ValueError."""
        with self.assertRaises(ValueError):
            self.service.get_product_details(123)  # type: ignore

    def test_result_is_isolated_copy(self):
        """La modification du résultat ne doit pas affecter l'état interne."""
        result = self.service.get_product_details("PROD-001")
        result["stock"] = 99999
        # Le catalogue interne ne doit pas avoir changé
        result2 = self.service.get_product_details("PROD-001")
        self.assertEqual(result2["stock"], 42)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Tests unitaires : update_stock
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateStock(unittest.TestCase):
    """Tests unitaires pour update_stock."""

    def setUp(self):
        self.service = InventoryService()

    def test_increment_stock(self):
        """Ajout de stock."""
        result = self.service.update_stock("PROD-001", 10)
        self.assertEqual(result["item_id"], "PROD-001")
        self.assertEqual(result["previous_stock"], 42)
        self.assertEqual(result["delta"], 10)
        self.assertEqual(result["new_stock"], 52)
        self.assertIn("timestamp", result)

    def test_decrement_stock(self):
        """Retrait de stock."""
        result = self.service.update_stock("PROD-001", -5)
        self.assertEqual(result["previous_stock"], 42)
        self.assertEqual(result["new_stock"], 37)

    def test_decrement_to_zero(self):
        """Retrait total du stock (résultat = 0) doit être autorisé."""
        result = self.service.update_stock("PROD-001", -42)
        self.assertEqual(result["new_stock"], 0)

    def test_negative_stock_raises(self):
        """Stock résultant < 0 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.update_stock("PROD-001", -99999)
        self.assertIn("insuffisant", str(ctx.exception))

    def test_unknown_product_raises(self):
        """Produit inconnu → ValueError."""
        with self.assertRaises(ValueError):
            self.service.update_stock("INCONNU", 5)

    def test_non_integer_delta_raises(self):
        """quantity_delta non-entier → ValueError."""
        with self.assertRaises(ValueError):
            self.service.update_stock("PROD-001", 5.5)  # type: ignore

    def test_bool_delta_raises(self):
        """quantity_delta bool → ValueError."""
        with self.assertRaises(ValueError):
            self.service.update_stock("PROD-001", True)  # type: ignore

    def test_empty_item_id_raises(self):
        """item_id vide → ValueError."""
        with self.assertRaises(ValueError):
            self.service.update_stock("", 5)

    def test_result_contains_timestamp_utc(self):
        """Le timestamp du résultat doit être UTC."""
        result = self.service.update_stock("PROD-003", 1)
        ts = result["timestamp"]
        self.assertTrue(ts.endswith("+00:00") or ts.endswith("Z"), f"Timestamp non-UTC : {ts}")

    def test_successive_updates(self):
        """Deux mises à jour successives accumulent correctement."""
        self.service.update_stock("PROD-004", 10)
        result = self.service.update_stock("PROD-004", -5)
        self.assertEqual(result["previous_stock"], 85)
        self.assertEqual(result["new_stock"], 80)

    def test_concurrent_updates_thread_safety(self):
        """10 threads concurrents incrémentent le stock — résultat cohérent."""
        service = InventoryService()
        initial = service.get_product_details("PROD-003")["stock"]  # 500
        errors = []

        def worker():
            try:
                service.update_stock("PROD-003", 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Erreurs rencontrées : {errors}")
        final = service.get_product_details("PROD-003")["stock"]
        self.assertEqual(final, initial + 50,
                         f"Attendu {initial + 50}, obtenu {final} — incohérence de concurrence")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Tests unitaires : stream_analytics
# ═══════════════════════════════════════════════════════════════════════════════

class TestStreamAnalytics(unittest.TestCase):
    """Tests unitaires pour stream_analytics."""

    def setUp(self):
        self.service = InventoryService()

    def test_cpu_usage_returns_list(self):
        """stream_analytics retourne une liste de dicts."""
        result = self.service.stream_analytics("cpu_usage")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 10)

    def test_event_structure(self):
        """Chaque événement contient les champs requis."""
        events = self.service.stream_analytics("cpu_usage", num_events=3)
        for event in events:
            self.assertIn("metric", event)
            self.assertIn("value", event)
            self.assertIn("unit", event)
            self.assertIn("timestamp", event)
            self.assertIn("sequence", event)

    def test_event_metric_name(self):
        """Le champ 'metric' correspond à la métrique demandée."""
        events = self.service.stream_analytics("memory_usage", num_events=2)
        for event in events:
            self.assertEqual(event["metric"], "memory_usage")

    def test_event_sequence_order(self):
        """Les séquences sont croissantes de 1 à N."""
        events = self.service.stream_analytics("request_rate", num_events=5)
        sequences = [e["sequence"] for e in events]
        self.assertEqual(sequences, [1, 2, 3, 4, 5])

    def test_event_values_in_range(self):
        """Les valeurs simulées restent dans l'intervalle défini."""
        for metric_name, spec in SUPPORTED_METRICS.items():
            events = self.service.stream_analytics(metric_name, num_events=10)
            for event in events:
                self.assertGreaterEqual(event["value"], spec["min_val"])
                self.assertLessEqual(event["value"], spec["max_val"])

    def test_event_unit_matches_spec(self):
        """L'unité correspond à la spécification de la métrique."""
        events = self.service.stream_analytics("error_rate", num_events=1)
        self.assertEqual(events[0]["unit"], "%")

    def test_all_supported_metrics(self):
        """Toutes les métriques supportées fonctionnent."""
        for metric_name in SUPPORTED_METRICS:
            events = self.service.stream_analytics(metric_name, num_events=1)
            self.assertEqual(len(events), 1)

    def test_custom_num_events(self):
        """num_events personnalisé."""
        events = self.service.stream_analytics("cpu_usage", num_events=25)
        self.assertEqual(len(events), 25)

    def test_unsupported_metric_raises(self):
        """Métrique inconnue → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.stream_analytics("disk_io")
        self.assertIn("non supportée", str(ctx.exception))

    def test_empty_metric_name_raises(self):
        """metric_name vide → ValueError."""
        with self.assertRaises(ValueError):
            self.service.stream_analytics("")

    def test_non_string_metric_raises(self):
        """metric_name non-string → ValueError."""
        with self.assertRaises(ValueError):
            self.service.stream_analytics(123)  # type: ignore

    def test_num_events_zero_raises(self):
        """num_events = 0 → ValueError."""
        with self.assertRaises(ValueError):
            self.service.stream_analytics("cpu_usage", num_events=0)

    def test_num_events_exceeds_limit_raises(self):
        """num_events > 100 → ValueError."""
        with self.assertRaises(ValueError):
            self.service.stream_analytics("cpu_usage", num_events=101)

    def test_result_is_json_serializable(self):
        """La liste retournée est entièrement sérialisable en JSON."""
        import json
        events = self.service.stream_analytics("cpu_usage", num_events=5)
        # Doit passer sans exception
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertIsInstance(serialized, str)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Test d'intégration RPC : RPCClient → TCP → RPCServer → InventoryService
# ═══════════════════════════════════════════════════════════════════════════════

class TestBusinessRPCIntegration(unittest.TestCase):
    """
    Tests d'intégration de bout en bout.

    Vérifie que les méthodes métier sont réellement accessibles à distance
    via le Custom RPC.

    Architecture testée :
        RPCClient → TCP → RPCServer → InventoryService
    """

    @classmethod
    def setUpClass(cls):
        """Démarre un serveur RPC connecté au service métier."""
        cls.service = InventoryService()
        cls.server = RPCServer(host="127.0.0.1", port=0)

        # Enregistrement dans la table blanche
        cls.server.register_method("calculate_factorial", cls.service.calculate_factorial)
        cls.server.register_method("get_product_details", cls.service.get_product_details)
        cls.server.register_method("update_stock", cls.service.update_stock)
        cls.server.register_method("stream_analytics", cls.service.stream_analytics)

        cls.server.start(threaded=True)
        cls.client = RPCClient(host="127.0.0.1", port=cls.server.port, timeout=5.0)

    @classmethod
    def tearDownClass(cls):
        """Arrête proprement le serveur."""
        cls.server.stop()

    def test_rpc_calculate_factorial(self):
        """Appel RPC distant : calculate_factorial(5) → 120."""
        result = self.client.calculate_factorial(n=5)
        self.assertEqual(result, 120)

    def test_rpc_get_product_details(self):
        """Appel RPC distant : get_product_details("PROD-001") → détails complets."""
        result = self.client.get_product_details(item_id="PROD-001")
        self.assertEqual(result["item_id"], "PROD-001")
        self.assertEqual(result["name"], "Laptop ProBook 450")
        self.assertIn("last_updated", result)

    def test_rpc_update_stock(self):
        """Appel RPC distant : update_stock("PROD-006", 5) → stock mis à jour."""
        result = self.client.update_stock(item_id="PROD-006", quantity_delta=5)
        self.assertEqual(result["delta"], 5)
        self.assertIn("new_stock", result)

    def test_rpc_stream_analytics(self):
        """Appel RPC distant : stream_analytics("cpu_usage") → liste d'événements."""
        result = self.client.stream_analytics(metric_name="cpu_usage", num_events=3)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["metric"], "cpu_usage")

    def test_rpc_factorial_error_propagation(self):
        """Erreur métier (n=-1) propagée correctement via RPC."""
        with self.assertRaises(RPCError) as ctx:
            self.client.calculate_factorial(n=-1)
        # L'erreur côté serveur est une ValueError → encapsulée en EXECUTION_ERROR
        self.assertEqual(ctx.exception.code, "EXECUTION_ERROR")
        self.assertIn("positif ou nul", ctx.exception.message)

    def test_rpc_unknown_product_error(self):
        """Erreur métier (produit inconnu) propagée correctement via RPC."""
        with self.assertRaises(RPCError) as ctx:
            self.client.get_product_details(item_id="FAKE-999")
        self.assertEqual(ctx.exception.code, "EXECUTION_ERROR")
        self.assertIn("introuvable", ctx.exception.message)

    def test_rpc_transparency(self):
        """Transparence de localisation : appel distant ressemble à appel local."""
        # Via stub dynamique
        result = self.client.calculate_factorial(n=10)
        self.assertEqual(result, 3628800)

        # Via call() explicite
        result2 = self.client.call("calculate_factorial", n=10)
        self.assertEqual(result2, 3628800)


if __name__ == "__main__":
    unittest.main()
