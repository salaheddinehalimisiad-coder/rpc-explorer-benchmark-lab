"""
Tests unitaires pour NetworkFaultSimulator (Phase 07).

Verifie :
1. L'initialisation par defaut
2. La configuration du timeout et la validation des delais
3. Le declenchement du crash brutal
4. La desactivation et la reinitalisation
"""

import time
import unittest
from failure_simulator.network_fault import NetworkFaultSimulator


class TestNetworkFaultSimulator(unittest.TestCase):
    """Suite de tests pour NetworkFaultSimulator."""

    def test_initialization_defaults(self):
        """Verifie l'etat par defaut a l'instanciation."""
        fault = NetworkFaultSimulator()
        self.assertFalse(fault.enabled)
        self.assertIsNone(fault.fault_type)
        self.assertEqual(fault.failure_delay, 0.0)
        self.assertIn("enabled=False", repr(fault))

    def test_simulate_timeout_configuration(self):
        """Verifie la configuration du mode timeout."""
        fault = NetworkFaultSimulator()
        fault.simulate_timeout(failure_delay_seconds=0.1)

        self.assertTrue(fault.enabled)
        self.assertEqual(fault.fault_type, "timeout")
        self.assertEqual(fault.failure_delay, 0.1)

        with self.assertRaises(ValueError):
            fault.simulate_timeout(failure_delay_seconds=0.0)

        with self.assertRaises(ValueError):
            fault.simulate_timeout(failure_delay_seconds=-1.0)

    def test_timeout_execution(self):
        """Verifie que check_and_apply bloque pendant le delai prevu."""
        fault = NetworkFaultSimulator()
        delay_s = 0.05
        fault.simulate_timeout(failure_delay_seconds=delay_s)

        t0 = time.perf_counter()
        fault.check_and_apply()
        elapsed = time.perf_counter() - t0

        self.assertGreaterEqual(elapsed, 0.04)
        self.assertLess(elapsed, 0.15)

    def test_simulate_server_crash_execution(self):
        """Verifie que check_and_apply leve ConnectionAbortedError en mode crash."""
        fault = NetworkFaultSimulator()
        fault.simulate_server_crash()

        self.assertTrue(fault.enabled)
        self.assertEqual(fault.fault_type, "crash")

        with self.assertRaises(ConnectionAbortedError) as ctx:
            fault.check_and_apply()
        self.assertIn("Simulated server crash", str(ctx.exception))

    def test_disable_cancels_fault(self):
        """Verifie que la desactivation empeche tout blocage ou exception."""
        fault = NetworkFaultSimulator()
        fault.simulate_server_crash()
        fault.disable()

        self.assertFalse(fault.enabled)
        self.assertIsNone(fault.fault_type)

        # Doit s'executer sans lever d'exception ni bloquer
        fault.check_and_apply()


if __name__ == "__main__":
    unittest.main()
