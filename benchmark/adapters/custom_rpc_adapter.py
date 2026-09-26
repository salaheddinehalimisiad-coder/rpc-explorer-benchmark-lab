"""
Adaptateur de benchmark pour le protocole Custom RPC (TCP + JSON).
"""

from typing import Dict, Any, Optional

from rpc_core.client_stub import RPCClient
from .base_adapter import BaseBenchmarkAdapter


class CustomRPCAdapter(BaseBenchmarkAdapter):
    """
    Adaptateur exécutant les appels via le client Custom RPC (framing TCP uint32 + JSON).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5000, client: Optional[RPCClient] = None):
        self.host = host
        self.port = port
        self.client = client if client is not None else RPCClient(host=host, port=port)

    @property
    def name(self) -> str:
        return "Custom RPC"

    def call_calculate_factorial(self, n: int) -> int:
        return self.client.call("calculate_factorial", n=n)

    def call_get_product_details(self, item_id: str) -> Dict[str, Any]:
        return self.client.call("get_product_details", item_id=item_id)

    def call_update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        return self.client.call("update_stock", item_id=item_id, quantity_delta=quantity_delta)

    def call_stream_analytics(self, metric_name: str, count: int = 5) -> Any:
        return self.client.call("stream_analytics", metric_name=metric_name, num_events=count)

    def close(self):
        # Le client Custom RPC ouvre/ferme ses sockets à chaque requête ou gère son état
        pass
