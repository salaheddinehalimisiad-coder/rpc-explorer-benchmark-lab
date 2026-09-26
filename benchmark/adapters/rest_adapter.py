"""
Adaptateur de benchmark pour le protocole REST (HTTP/1.1 + JSON).
"""

from typing import Dict, Any, Optional

from rest.rest_client import RestClient
from .base_adapter import BaseBenchmarkAdapter


class RESTAdapter(BaseBenchmarkAdapter):
    """
    Adaptateur exécutant les appels via le client HTTP/REST (Flask + JSON).
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5001",
        client: Optional[RestClient] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.client = client if client is not None else RestClient(base_url=self.base_url)

    @property
    def name(self) -> str:
        return "REST"

    def call_calculate_factorial(self, n: int) -> int:
        return self.client.calculate_factorial(n)

    def call_get_product_details(self, item_id: str) -> Dict[str, Any]:
        return self.client.get_product_details(item_id)

    def call_update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        return self.client.update_stock(item_id, quantity_delta)

    def call_stream_analytics(self, metric_name: str, count: int = 5) -> Any:
        return self.client.stream_analytics(metric_name, count=count)

    def close(self):
        self.client.close()
