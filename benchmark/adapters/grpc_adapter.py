"""
Adaptateur de benchmark pour le protocole gRPC (HTTP/2 + Protobuf binaire).
"""

from typing import Dict, Any, Optional

from grpc.grpc_client import InventoryGRPCClient
from .base_adapter import BaseBenchmarkAdapter


class GRPCAdapter(BaseBenchmarkAdapter):
    """
    Adaptateur exécutant les appels via le client gRPC (Protobuf IDL + HTTP/2).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        client: Optional[InventoryGRPCClient] = None,
    ):
        self.host = host
        self.port = port
        self.client = client if client is not None else InventoryGRPCClient(host=host, port=port)
        self.client.connect()

    @property
    def name(self) -> str:
        return "gRPC"

    def call_calculate_factorial(self, n: int) -> int:
        return self.client.calculate_factorial(n)

    def call_get_product_details(self, item_id: str) -> Dict[str, Any]:
        return self.client.get_product_details(item_id)

    def call_update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        return self.client.update_stock(item_id, quantity_delta)

    def call_stream_analytics(self, metric_name: str, count: int = 5) -> Any:
        # Consomme l'intégralité du stream pour mesurer le coût total de réception
        return list(self.client.stream_analytics(metric_name, count=count))

    def close(self):
        self.client.close()
