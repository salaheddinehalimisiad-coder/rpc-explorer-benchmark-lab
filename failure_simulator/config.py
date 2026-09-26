"""
Configuration des scenarios de pannes pour FailureSimulator (Phase 07).

Definit les structures de donnees et les presets de simulation
pour assurer la reproductibilite et le determinisme des campagnes de test.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class FailureConfig:
    """
    Configuration d'un scenario de panne.

    Attributs :
        scenario_name: Identifiant lisible du scenario.
        latency_ms: Delai artificiel en millisecondes a injecter.
        fault_type: Type de defaillance reseau ("timeout", "crash", ou None).
        failure_delay: Delai en secondes pour le mode timeout.
        description: Description pedagogique de l'effet attendu.
    """
    scenario_name: str = "nominal"
    latency_ms: float = 0.0
    fault_type: Optional[str] = None
    failure_delay: float = 0.0
    description: str = "Comportement nominal sans anomalie injectee."
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_fault_configured(self) -> bool:
        """Retourne True si une anomalie (latence ou panne) est configuree."""
        return self.latency_ms > 0 or self.fault_type is not None


# Presets de test standardises pour benchmarks et demos
PRESET_NOMINAL = FailureConfig(
    scenario_name="nominal",
    latency_ms=0.0,
    fault_type=None,
    failure_delay=0.0,
    description="Baseline normale sans injection d'anomalie."
)

PRESET_LATENCY_50MS = FailureConfig(
    scenario_name="latency_50ms",
    latency_ms=50.0,
    fault_type=None,
    failure_delay=0.0,
    description="Injection d'une latence artificielle moderee de 50ms."
)

PRESET_LATENCY_200MS = FailureConfig(
    scenario_name="latency_200ms",
    latency_ms=200.0,
    fault_type=None,
    failure_delay=0.0,
    description="Injection d'une latence artificielle forte de 200ms."
)

PRESET_TIMEOUT_3S = FailureConfig(
    scenario_name="timeout_3s",
    latency_ms=0.0,
    fault_type="timeout",
    failure_delay=3.0,
    description="Suspension de 3.0s pour declencher un timeout client."
)

PRESET_SERVER_CRASH = FailureConfig(
    scenario_name="server_crash",
    latency_ms=0.0,
    fault_type="crash",
    failure_delay=0.0,
    description="Simulation de crash / coupure brutale du serveur."
)
