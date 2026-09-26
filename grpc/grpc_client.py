"""
Client gRPC pour le Service d'Inventaire et de Calcul

Consomme le service gRPC via les stubs générés par protoc.

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 04.
"""

from typing import Dict, Any, Iterator


class InventoryGRPCClient:
    """
    Client gRPC consommant le service distribué via un canal gRPC et stub typé.
    """

    def __init__(self, host: str = "localhost", port: int = 50051):
        self.host = host
        self.port = port
        self.channel = None
        self.stub = None

    def calculate_factorial(self, n: int) -> int:
        """Appel unaire vers CalculateFactorial via gRPC."""
        raise NotImplementedError("calculate_factorial sera implémenté en Phase 04")

    def get_product_details(self, item_id: str) -> Dict[str, Any]:
        """Appel unaire vers GetProductDetails via gRPC."""
        raise NotImplementedError("get_product_details sera implémenté en Phase 04")

    def update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """Appel unaire vers UpdateStock via gRPC."""
        raise NotImplementedError("update_stock sera implémenté en Phase 04")

    def stream_analytics(self, metric_name: str, count: int = 5) -> Iterator[Dict[str, Any]]:
        """Appel Server Streaming vers StreamAnalytics via gRPC."""
        raise NotImplementedError("stream_analytics sera implémenté en Phase 04")
        if False:
            yield {}

    def close(self):
        """Ferme le canal gRPC."""
        pass
