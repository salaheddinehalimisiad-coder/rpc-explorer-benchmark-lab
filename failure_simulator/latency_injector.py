"""
Module d'injection de latence artificielle.

Permet de simuler les delais reseau dans les communications RPC
pour observer concretement la difference entre un appel local en memoire (quasi-instantane)
et un appel distant soumis aux aleas du reseau.
"""

import time
from typing import Optional


class LatencyInjector:
    """
    Injecte un delai artificiel dans les appels RPC pour simuler la latence reseau.

    Attributs :
        delay_ms (float) : Delai en millisecondes a injecter.
        enabled (bool) : Indicateur d'activation de l'injection.
    """

    def __init__(self, delay_ms: float = 0.0) -> None:
        if delay_ms < 0:
            raise ValueError("delay_ms must be non-negative")
        self.delay_ms = float(delay_ms)
        self.enabled = False

    def enable(self, delay_ms: Optional[float] = None) -> None:
        """
        Active l'injection de latence.

        Args:
            delay_ms: Delai optionnel en ms a appliquer. Si omis, conserve la valeur actuelle.
        """
        if delay_ms is not None:
            if delay_ms < 0:
                raise ValueError("delay_ms must be non-negative")
            self.delay_ms = float(delay_ms)
        self.enabled = True

    def disable(self) -> None:
        """Desactive l'injection de latence."""
        self.enabled = False

    def inject(self) -> float:
        """
        Injecte la latence configuree si l'injecteur est active et delay_ms > 0.

        Returns:
            Le delai theorique attendu en secondes (0.0 si inactif ou delai <= 0).
        """
        if self.enabled and self.delay_ms > 0:
            delay_s = self.delay_ms / 1000.0
            time.sleep(delay_s)
            return delay_s
        return 0.0

    def __repr__(self) -> str:
        return f"<LatencyInjector enabled={self.enabled} delay_ms={self.delay_ms}>"
