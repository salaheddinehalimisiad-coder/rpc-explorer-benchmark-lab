"""
Interface de base pour les adaptateurs de benchmark.

Permet d'exécuter des tests comparatifs de manière uniforme sur Local, Custom RPC, gRPC et REST.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseBenchmarkAdapter(ABC):
    """
    Interface abstraite pour brancher n'importe quel protocole dans le BenchmarkRunner.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du protocole / technologie (ex: 'Custom RPC', 'gRPC', 'REST', 'Local')."""
        pass

    @abstractmethod
    def call_calculate_factorial(self, n: int) -> int:
        """Exécute l'appel de calcul."""
        pass

    @abstractmethod
    def call_get_product_details(self, item_id: str) -> Dict[str, Any]:
        """Exécute l'appel de lecture produit."""
        pass

    @abstractmethod
    def call_update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """Exécute l'appel de mise à jour de stock."""
        pass
