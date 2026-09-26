"""
Tests unitaires pour l'orchestrateur FailureSimulator (Phase 07).

Verifie :
1. L'instanciation, les attributs et l'etat initial
2. L'activation des scenarios (latence, timeout, crash, server_down)
3. L'application des profils FailureConfig
4. L'execution des hooks pre-execution
5. La reinitialisation et l'isolation des instances
6. Le reporting d'etat (get_status)
"""

import time
import unittest
from failure_simulator.simulator import FailureSimulator
from failure_simulator.config import (
    FailureConfig,
    PRESET_NOMINAL,
    PRESET_LATENCY_50MS,
    PRESET_TIMEOUT_3S,
    PRESET_SERVER_CRASH,
)


class TestFailureSimulator(unittest.TestCase):
    """Suite de tests pour FailureSimulator."""

    def test_initialization_defaults(self):
        """Verifie les valeurs par defaut du simulateur."""
        sim = FailureSimulator()
        self.assertFalse(sim.is_active)
        self.assertIsNone(sim.active_scenario)
        self.assertEqual(sim.latency_ms, 0.0)
        self.assertFalse(sim.latency_injector.enabled)
        self.assertFalse(sim.network_fault.enabled)
        self.assertIn("active=False", repr(sim))

    def test_initialization_with_latency(self):
        """Verifie l'initialisation directe avec latence."""
        sim = FailureSimulator(latency_ms=100.0)
        self.assertTrue(sim.is_active)
        self.assertEqual(sim.latency_ms, 100.0)
        self.assertTrue(sim.latency_injector.enabled)
        self.assertEqual(sim.active_scenario, "latency_100.0ms")

    def test_enable_latency_spike(self):
        """Verifie l'activation du scenario de pic de latence."""
        sim = FailureSimulator()
        sim.enable_latency_spike(delay_ms=250.0)

        self.assertTrue(sim.is_active)
        self.assertEqual(sim.latency_ms, 250.0)
        self.assertTrue(sim.latency_injector.enabled)
        self.assertEqual(sim.active_scenario, "latency_250.0ms")

    def test_simulate_timeout(self):
        """Verifie la configuration du scenario timeout."""
        sim = FailureSimulator()
        sim.simulate_timeout(failure_delay_seconds=2.5)

        self.assertTrue(sim.is_active)
        self.assertEqual(sim.network_fault.fault_type, "timeout")
        self.assertEqual(sim.network_fault.failure_delay, 2.5)
        self.assertEqual(sim.active_scenario, "timeout_2.5s")

    def test_simulate_server_crash_and_server_down(self):
        """Verifie la configuration du crash serveur et server_down."""
        sim = FailureSimulator()
        sim.simulate_server_crash()

        self.assertTrue(sim.is_active)
        self.assertEqual(sim.network_fault.fault_type, "crash")
        self.assertEqual(sim.active_scenario, "server_crash")

        sim2 = FailureSimulator()
        sim2.simulate_server_down()
        self.assertTrue(sim2.is_active)
        self.assertEqual(sim2.network_fault.fault_type, "crash")

    def test_contract_breaking_change_placeholder(self):
        """Verifie que simulate_contract_breaking_change leve NotImplementedError reserve pour Phase 10."""
        sim = FailureSimulator()
        with self.assertRaises(NotImplementedError) as ctx:
            sim.simulate_contract_breaking_change()
        self.assertIn("Phase 10", str(ctx.exception))

    def test_apply_config_presets(self):
        """Verifie l'application de configurations declarees."""
        sim = FailureSimulator()

        # Preset Latence
        sim.apply_config(PRESET_LATENCY_50MS)
        self.assertTrue(sim.is_active)
        self.assertEqual(sim.latency_ms, 50.0)
        self.assertIsNone(sim.network_fault.fault_type)

        # Preset Crash
        sim.apply_config(PRESET_SERVER_CRASH)
        self.assertTrue(sim.is_active)
        self.assertFalse(sim.latency_injector.enabled)
        self.assertEqual(sim.network_fault.fault_type, "crash")

        # Preset Nominal
        sim.apply_config(PRESET_NOMINAL)
        self.assertFalse(sim.is_active)
        self.assertFalse(sim.latency_injector.enabled)
        self.assertFalse(sim.network_fault.enabled)

    def test_apply_pre_execution_hooks_nominal(self):
        """Verifie que les hooks ne font rien en mode nominal inactif."""
        sim = FailureSimulator()
        t0 = time.perf_counter()
        sim.apply_pre_execution_hooks()
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 0.02)

    def test_apply_pre_execution_hooks_latency(self):
        """Verifie que les hooks injectent la latence lorsqu'elle est activee."""
        sim = FailureSimulator()
        sim.enable_latency_spike(delay_ms=30.0)

        t0 = time.perf_counter()
        sim.apply_pre_execution_hooks()
        elapsed = time.perf_counter() - t0

        self.assertGreaterEqual(elapsed, 0.025)
        self.assertLess(elapsed, 0.080)

    def test_apply_pre_execution_hooks_crash(self):
        """Verifie que les hooks levent ConnectionAbortedError en mode crash."""
        sim = FailureSimulator()
        sim.simulate_server_crash()

        with self.assertRaises(ConnectionAbortedError):
            sim.apply_pre_execution_hooks()

    def test_reset_and_isolation(self):
        """Verifie que le reset remet a zero et que deux instances sont strictement independantes."""
        sim1 = FailureSimulator()
        sim2 = FailureSimulator()

        sim1.enable_latency_spike(100.0)
        sim1.simulate_server_crash()

        self.assertTrue(sim1.is_active)
        self.assertFalse(sim2.is_active)

        sim1.reset()
        self.assertFalse(sim1.is_active)
        self.assertIsNone(sim1.active_scenario)

    def test_get_status(self):
        """Verifie le dictionnaire de statut."""
        sim = FailureSimulator()
        status = sim.get_status()
        self.assertFalse(status["is_active"])
        self.assertFalse(status["latency_enabled"])
        self.assertFalse(status["fault_enabled"])

        sim.enable_latency_spike(75.0)
        status2 = sim.get_status()
        self.assertTrue(status2["is_active"])
        self.assertTrue(status2["latency_enabled"])
        self.assertEqual(status2["latency_ms"], 75.0)


if __name__ == "__main__":
    unittest.main()
