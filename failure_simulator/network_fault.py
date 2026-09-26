"""
Module de simulation de pannes reseau (Phase 07).

Fournit des mecanismes configurables pour reproduire les defaillances reseau courantes
rencontrees dans les systemes distribues :
- Timeout serveur (delai de reponse superieur au timeout configure par le client)
- Crash / coupure brutale du serveur (ConnectionAbortedError)
- Observation de connection refused (quand le serveur est eteint)
"""

import time
from typing import Optional


class NetworkFaultSimulator:
    """
    Simulateur d'anomalies et d'interruptions reseau.

    Permet de configurer des comportements d'echec reproductibles au niveau
    du point d'entree du serveur RPC pour evaluer la resilience du client.
    """

    def __init__(self) -> None:
        self.fault_type: Optional[str] = None
        self.failure_delay: float = 0.0
        self.enabled: bool = False

    def simulate_timeout(self, failure_delay_seconds: float = 5.0) -> None:
        """
        Configure une panne de type TIMEOUT.
        Le serveur suspendra son traitement pendant failure_delay_seconds,
        ce qui provoquera un depassement du delai d'attente (timeout) chez le client
        si client_timeout < failure_delay_seconds.

        Args:
            failure_delay_seconds: Duree d'attente en secondes (defaut: 5.0s).
        """
        if failure_delay_seconds <= 0:
            raise ValueError("failure_delay_seconds must be positive")
        self.fault_type = "timeout"
        self.failure_delay = float(failure_delay_seconds)
        self.enabled = True

    def simulate_server_crash(self) -> None:
        """
        Configure une simulation de crash serveur brutal.
        Provoque une ConnectionAbortedError lors du traitement de la requete.
        """
        self.fault_type = "crash"
        self.failure_delay = 0.0
        self.enabled = True

    def disable(self) -> None:
        """Desactive les simulations de panne reseau."""
        self.enabled = False
        self.fault_type = None
        self.failure_delay = 0.0

    def check_and_apply(self) -> None:
        """
        Verifie et execute la panne configuree si activee.

        Raises:
            ConnectionAbortedError: Si le mode crash est active.
        """
        if not self.enabled:
            return

        if self.fault_type == "timeout":
            time.sleep(self.failure_delay)
        elif self.fault_type == "crash":
            raise ConnectionAbortedError("Simulated server crash / brutal disconnection")

    def __repr__(self) -> str:
        return (
            f"<NetworkFaultSimulator enabled={self.enabled} "
            f"fault_type={self.fault_type} delay={self.failure_delay}s>"
        )
