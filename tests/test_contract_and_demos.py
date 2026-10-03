"""
Tests de la Phase 10 (évolution de contrat) et des démonstrations pédagogiques.
Ces tests vérifient les COMPORTEMENTS observés, pas seulement que le code tourne.
"""

import io
import unittest
from contextlib import redirect_stdout

from contract_evolution.demo import (BREAKING_LOUD, BREAKING_SILENT, COMPATIBLE,
                                     run_custom_rpc_scenarios, run_grpc_scenarios)
from lab import failures


def _by_scenario(rows):
    return {r["scenario"]: r for r in rows}


class TestContractEvolution(unittest.TestCase):
    def test_custom_rpc_scenarios(self):
        rows = _by_scenario(run_custom_rpc_scenarios())
        self.assertEqual(rows["Client v1 → Serveur v1"]["verdict"], COMPATIBLE)
        self.assertEqual(rows["get_product_details"]["verdict"], COMPATIBLE)
        self.assertEqual(rows["update_stock"]["verdict"], BREAKING_LOUD)
        self.assertIn("INVALID_ARGS", rows["update_stock"]["observed"])
        self.assertIn("METHOD_NOT_FOUND", rows["calculate_factorial"]["observed"])

    def test_grpc_scenarios_against_v2_process(self):
        rows = _by_scenario(run_grpc_scenarios())
        self.assertEqual(rows["Client v1 → Serveur v1"]["verdict"], COMPATIBLE)
        self.assertEqual(rows["GetProductDetails"]["verdict"], COMPATIBLE)
        # Le renumérotage ne lève AUCUNE erreur : bug silencieux, stock inchangé (42)
        self.assertEqual(rows["UpdateStock"]["verdict"], BREAKING_SILENT)
        self.assertIn("stock = 42", rows["UpdateStock"]["observed"])
        self.assertIn("INVALID_ARGUMENT", rows["CalculateFactorial"]["observed"])
        self.assertIn("UNIMPLEMENTED", rows["StreamAnalytics"]["observed"])


class TestFailureDemo(unittest.TestCase):
    def _quiet(self, fn, *a, **kw):
        with redirect_stdout(io.StringIO()):
            return fn(*a, **kw)

    def test_latency_is_added_to_remote_calls_only(self):
        rows = self._quiet(failures.scenario_latency, delays_ms=(0, 60))
        injected = rows[1]
        for proto in ("custom_rpc", "grpc", "rest"):
            self.assertGreaterEqual(injected[proto], 55)
        self.assertLess(injected["local"], 5)

    def test_timeouts_cut_the_wait(self):
        rows = self._quiet(failures.scenario_timeout, server_delay_s=1.0, client_timeout_s=0.2)
        for r in rows:
            self.assertNotIn("succès", r["erreur"])
            self.assertLess(r["attente_ms"], 900)
        self.assertIn("DEADLINE_EXCEEDED", rows[1]["erreur"])
        self.assertIn("TIMEOUT", rows[2]["erreur"])

    def test_server_down(self):
        rows = {r["protocole"]: r["resultat"] for r in self._quiet(failures.scenario_server_down)}
        self.assertTrue(rows["Local"].startswith("OK"))
        self.assertIn("ConnectionError", rows["Custom RPC"])
        self.assertIn("UNAVAILABLE", rows["gRPC"])
        self.assertIn("CONNECTION_ERROR", rows["REST"])

    def test_retry_recovers_after_restart(self):
        res = self._quiet(failures.scenario_retry_on_restart, restart_after_s=0.3)
        self.assertIn("CRASH", res["naive"])
        self.assertTrue(res["robust"].startswith("succès"))

    def test_retry_on_non_idempotent_operation_doubles_effect(self):
        res = self._quiet(failures.scenario_retry_not_idempotent)
        self.assertEqual(res["naif"]["retire"], 2)
        self.assertEqual(res["idempotent"]["retire"], 1)


if __name__ == "__main__":
    unittest.main()
