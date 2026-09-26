"""
Client REST HTTP / JSON

Client consommant l'API REST via requêtes HTTP standard (GET/POST) pour comparaison avec les stubs RPC.

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 05.
"""

from typing import Dict, Any


class RestClient:
    """
    Client REST pour effectuer des appels HTTP vers le serveur REST.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        self.base_url = base_url.rstrip("/")

    def calculate_factorial(self, n: int) -> int:
        """Appel POST /api/factorial."""
        raise NotImplementedError("calculate_factorial sera implémenté en Phase 05")

    def get_product_details(self, item_id: str) -> Dict[str, Any]:
        """Appel GET /api/products/{item_id}."""
        raise NotImplementedError("get_product_details sera implémenté en Phase 05")

    def update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """Appel POST /api/products/{item_id}/stock."""
        raise NotImplementedError("update_stock sera implémenté en Phase 05")
