"""
Orchestrateur central du Failure Simulator (Phase 07).

Fournit une interface unifiee et isolee pour piloter les scenarios d'anomalies
(latence, timeouts, deconnexions, corruptions) et observer leur impact
sur les differents transports RPC (Custom RPC, gRPC, REST).
"""

from typing import Any, Dict, Optional
from .latency_injector import LatencyInjector
from .network_fault import NetworkFaultSimulator
from .message_corruptor import MessageCorruptor
from .config import FailureConfig


class FailureSimulator:
    """
    Gestionnaire central et orchestrateur d'injection d'anomalies reseau.

    Chaque instance de FailureSimulator est isolee pour empecher la contamination
    entre campagnes de test ou benchmarks successifs.
    """

    def __init__(self, latency_ms: float = 0.0, drop_rate: float = 0.0) -> None:
        """
        Initialise le simulateur de pannes.

        Args:
            latency_ms: Latence initiale optionnelle en ms.
            drop_rate: Taux de perte initialise (reserve pour usage futur).
        """
        self.latency_injector = LatencyInjector(delay_ms=latency_ms)
        self.network_fault = NetworkFaultSimulator()
        self.corruptor = MessageCorruptor()
        self.drop_rate = drop_rate
        self.active_scenario: Optional[str] = None

        if latency_ms > 0:
            self.latency_injector.enable(latency_ms)
            self.active_scenario = f"latency_{latency_ms}ms"

    @property
    def latency_ms(self) -> float:
        """Retourne la latence configuree dans l'injecteur."""
        return self.latency_injector.delay_ms

    @latency_ms.setter
    def latency_ms(self, val: float) -> None:
        self.latency_injector.delay_ms = float(val)

    @property
    def is_active(self) -> bool:
        """Retourne True si une anomalie (latence ou defaillance reseau) est active."""
        return self.latency_injector.enabled or self.network_fault.enabled

    def enable_latency_spike(self, delay_ms: float = 200.0) -> None:
        """
        Active une latence artificielle sur les appels entrants.

        Args:
            delay_ms: Duree du delai en ms (defaut: 200.0ms).
        """
        self.latency_injector.enable(delay_ms)
        self.active_scenario = f"latency_{delay_ms}ms"

    def simulate_timeout(self, failure_delay_seconds: float = 5.0) -> None:
        """
        Simule un depassement de delai (timeout) en retardant la reponse serveur.

        Args:
            failure_delay_seconds: Duree de retention avant reponse en secondes.
        """
        self.network_fault.simulate_timeout(failure_delay_seconds)
        self.active_scenario = f"timeout_{failure_delay_seconds}s"

    def simulate_server_crash(self) -> None:
        """Simule un crash serveur brutal interrompant la requete."""
        self.network_fault.simulate_server_crash()
        self.active_scenario = "server_crash"

    def simulate_server_down(self) -> None:
        """
        Simule un serveur indisponible / eteint.
        Active la simulation de crash cote serveur ou represente l'etat hors-ligne.
        """
        self.simulate_server_crash()

    def simulate_contract_breaking_change(self) -> None:
        """
        Placeholder reserve pour la Phase 10 (Contract Evolution / Breaking Changes).
        """
        raise NotImplementedError("simulate_contract_breaking_change sera implemente en Phase 10")

    def apply_config(self, config: FailureConfig) -> None:
        """
        Applique un profil de configuration complet.

        Args:
            config: Objet FailureConfig definissant le scenario.
        """
        self.reset()
        self.active_scenario = config.scenario_name

        if config.latency_ms > 0:
            self.latency_injector.enable(config.latency_ms)

        if config.fault_type == "timeout":
            self.network_fault.simulate_timeout(config.failure_delay)
        elif config.fault_type == "crash":
            self.network_fault.simulate_server_crash()

    def apply_pre_execution_hooks(self) -> None:
        """
        Point d'entree unifie a appeler par les serveurs avant l'execution d'une methode.
        Applique d'abord la latence artificielle puis verifie les pannes reseau.

        Raises:
            ConnectionAbortedError: Si le crash serveur est simule.
        """
        if self.latency_injector.enabled:
            self.latency_injector.inject()

        if self.network_fault.enabled:
            self.network_fault.check_and_apply()

    def reset(self) -> None:
        """Reinitialise tous les injecteurs a l'etat inactif nominal."""
        self.latency_injector.disable()
        self.network_fault.disable()
        self.active_scenario = None

    def get_status(self) -> Dict[str, Any]:
        """Retourne l'etat actuel du simulateur."""
        return {
            "is_active": self.is_active,
            "active_scenario": self.active_scenario,
            "latency_enabled": self.latency_injector.enabled,
            "latency_ms": self.latency_injector.delay_ms,
            "fault_enabled": self.network_fault.enabled,
            "fault_type": self.network_fault.fault_type,
            "failure_delay": self.network_fault.failure_delay,
            "drop_rate": self.drop_rate,
        }

    def __repr__(self) -> str:
        return (
            f"<FailureSimulator active={self.is_active} "
            f"scenario={self.active_scenario} "
            f"latency={self.latency_injector.delay_ms}ms "
            f"fault={self.network_fault.fault_type}>"
        )
