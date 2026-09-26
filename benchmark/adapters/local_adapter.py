"""
Adaptateur de benchmark pour les appels en mémoire locale.

Sert de baseline 'zéro-réseau' et 'zéro-sérialisation' pour quantifier le coût
des middlewares distribués (Custom RPC, gRPC, REST).
"""

from typing import Dict, Any, Optional

from business.inventory_service import InventoryService
from .base_adapter import BaseBenchmarkAdapter


class LocalAdapter(BaseBenchmarkAdapter):
    """
    Adaptateur exécutant les appels directement en mémoire sur une instance d'InventoryService.
    """

    def __init__(self, service: Optional[InventoryService] = None):
        self.service = service if service is not None else InventoryService()

    @property
    def name(self) -> str:
        return "Local"

    def call_calculate_factorial(self, n: int) -> int:
        return self.service.calculate_factorial(n)

    def call_get_product_details(self, item_id: str) -> Dict[str, Any]:
        return self.service.get_product_details(item_id)

    def call_update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        return self.service.update_stock(item_id, quantity_delta)

    def call_stream_analytics(self, metric_name: str, count: int = 5) -> Any:
        return self.service.stream_analytics(metric_name, count)

    def close(self):
        pass
