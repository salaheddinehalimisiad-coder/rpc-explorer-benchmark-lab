"""
Tests unitaires pour LatencyInjector (Phase 07).

Verifie :
1. L'initialisation et validation des arguments
2. L'activation / desactivation
3. L'absence d'impact lorsque desactive
4. L'injection effective de delais avec precision raisonnable (tolerance OS/Python)
"""

import time
import unittest
from failure_simulator.latency_injector import LatencyInjector


class TestLatencyInjector(unittest.TestCase):
    """Suite de tests pour LatencyInjector."""

    def test_initialization_defaults(self):
        """Verifie les valeurs par defaut a l'instanciation."""
        injector = LatencyInjector()
        self.assertEqual(injector.delay_ms, 0.0)
        self.assertFalse(injector.enabled)
        self.assertIn("enabled=False", repr(injector))

    def test_initialization_with_delay(self):
        """Verifie l'instanciation avec un delai initial."""
        injector = LatencyInjector(delay_ms=150.0)
        self.assertEqual(injector.delay_ms, 150.0)
        self.assertFalse(injector.enabled)

    def test_initialization_negative_delay_raises_value_error(self):
        """Verifie qu'un delai negatif leve ValueError."""
        with self.assertRaises(ValueError):
            LatencyInjector(delay_ms=-10.0)

    def test_enable_and_disable(self):
        """Verifie l'activation et desactivation sans modifier le delai."""
        injector = LatencyInjector(delay_ms=50.0)
        self.assertFalse(injector.enabled)

        injector.enable()
        self.assertTrue(injector.enabled)
        self.assertEqual(injector.delay_ms, 50.0)

        injector.disable()
        self.assertFalse(injector.enabled)

    def test_enable_with_new_delay(self):
        """Verifie l'activation en fournissant un nouveau delai."""
        injector = LatencyInjector(delay_ms=50.0)
        injector.enable(delay_ms=200.0)
        self.assertTrue(injector.enabled)
        self.assertEqual(injector.delay_ms, 200.0)

        with self.assertRaises(ValueError):
            injector.enable(delay_ms=-5.0)

    def test_inject_when_disabled(self):
        """Verifie qu'aucune latence n'est injectee si l'injecteur est desactive."""
        injector = LatencyInjector(delay_ms=500.0)
        t0 = time.perf_counter()
        returned = injector.inject()
        elapsed = time.perf_counter() - t0

        self.assertEqual(returned, 0.0)
        self.assertLess(elapsed, 0.02)  # Doit s'executer quasi-instantanement (< 20ms)

    def test_inject_when_enabled_zero_delay(self):
        """Verifie qu'un delai de 0.0 ms n'injecte rien meme si active."""
        injector = LatencyInjector(delay_ms=0.0)
        injector.enable()
        t0 = time.perf_counter()
        returned = injector.inject()
        elapsed = time.perf_counter() - t0

        self.assertEqual(returned, 0.0)
        self.assertLess(elapsed, 0.02)

    def test_inject_when_enabled_nominal(self):
        """Verifie que l'injection applique bien le delai attendu (tolerance +-25% pour scheduler OS)."""
        target_delay_ms = 40.0
        injector = LatencyInjector(delay_ms=target_delay_ms)
        injector.enable()

        t0 = time.perf_counter()
        returned = injector.inject()
        elapsed_s = time.perf_counter() - t0

        self.assertEqual(returned, target_delay_ms / 1000.0)
        # Tolerance realiste pour time.sleep sous Windows
        self.assertGreaterEqual(elapsed_s, 0.030)  # Au moins 30ms
        self.assertLess(elapsed_s, 0.090)          # Moins de 90ms


if __name__ == "__main__":
    unittest.main()
