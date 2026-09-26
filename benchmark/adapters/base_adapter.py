"""
Interface de base pour les adaptateurs de benchmark.

Permet d'exécuter des tests comparatifs de manière uniforme sur Local, Custom RPC, gRPC et REST.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseBenchmarkAdapter(ABC):
    """
    Interface abstraite pour brancher n'importe quel protocole dans le BenchmarkRunner.
    Garantit une signature commune pour toutes les opérations de test.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du protocole / technologie (ex: 'Local', 'Custom RPC', 'gRPC', 'REST')."""
        pass

    @abstractmethod
    def call_calculate_factorial(self, n: int) -> int:
        """Exécute l'appel de calcul factorielle."""
        pass

    @abstractmethod
    def call_get_product_details(self, item_id: str) -> Dict[str, Any]:
        """Exécute l'appel de lecture des détails d'un produit."""
        pass

    @abstractmethod
    def call_update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """Exécute l'appel de mise à jour de stock."""
        pass

    @abstractmethod
    def call_stream_analytics(self, metric_name: str, count: int = 5) -> Any:
        """Exécute l'appel de métriques / télémétrie."""
        pass

    def close(self):
        """Libère les ressources de connexion (sockets, channels gRPC, sessions HTTP)."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
