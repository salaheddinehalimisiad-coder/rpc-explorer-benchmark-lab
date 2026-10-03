"""
Client gRPC pour le Service d'Inventaire et de Calcul

Consomme le service gRPC via les stubs générés par protoc.
Prend en charge les appels unaires et le Server Streaming avec typage strict.
Conforme au contrat protos/inventory.proto et au cahier des charges officiel.
"""

from typing import Dict, Any, Iterator, Optional

import grpc

from protos import inventory_pb2
from protos import inventory_pb2_grpc


class InventoryGRPCClient:
    """
    Client gRPC consommant le service distribué via un canal gRPC et stub typé.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        timeout: float = 10.0,
        interceptors: Optional[list] = None,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        # Intercepteurs client optionnels (ex: inspecteur "Sous le capot")
        self.interceptors = list(interceptors or [])
        self.channel: Optional[grpc.Channel] = None
        self.stub: Optional[inventory_pb2_grpc.InventoryRPCServiceStub] = None

    def connect(self):
        """Établit le canal gRPC et instancie le stub s'ils ne sont pas déjà actifs."""
        if self.channel is None:
            self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
            if self.interceptors:
                self.channel = grpc.intercept_channel(self.channel, *self.interceptors)
            self.stub = inventory_pb2_grpc.InventoryRPCServiceStub(self.channel)

    def _ensure_connected(self):
        """Vérifie que la connexion est établie."""
        if self.stub is None:
            self.connect()

    def calculate_factorial(self, n: int) -> int:
        """
        Appel unaire vers CalculateFactorial via gRPC.
        Retourne la valeur de la factorielle.
        """
        self._ensure_connected()
        req = inventory_pb2.FactorialRequest(n=n)
        response: inventory_pb2.FactorialResponse = self.stub.CalculateFactorial(
            req, timeout=self.timeout
        )
        return response.result

    def calculate_factorial_with_metadata(self, n: int) -> Dict[str, Any]:
        """
        Variante d'appel retournant à la fois le résultat et le temps d'exécution serveur (ms).
        """
        self._ensure_connected()
        req = inventory_pb2.FactorialRequest(n=n)
        response: inventory_pb2.FactorialResponse = self.stub.CalculateFactorial(
            req, timeout=self.timeout
        )
        return {
            "result": response.result,
            "execution_time_ms": response.execution_time_ms,
        }

    def get_product_details(self, item_id: str) -> Dict[str, Any]:
        """
        Appel unaire vers GetProductDetails via gRPC.
        Retourne un dictionnaire contenant les attributs du produit.
        """
        self._ensure_connected()
        req = inventory_pb2.ProductRequest(item_id=item_id)
        response: inventory_pb2.ProductResponse = self.stub.GetProductDetails(
            req, timeout=self.timeout
        )
        return {
            "item_id": response.item_id,
            "name": response.name,
            "quantity": response.quantity,
            "unit_price": response.unit_price,
            "category": response.category,
            "success": response.success,
            "message": response.message,
        }

    def update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """
        Appel unaire vers UpdateStock via gRPC.
        Retourne le résultat de la mutation de stock.
        """
        self._ensure_connected()
        req = inventory_pb2.UpdateStockRequest(
            item_id=item_id, quantity_delta=quantity_delta
        )
        response: inventory_pb2.ProductResponse = self.stub.UpdateStock(
            req, timeout=self.timeout
        )
        return {
            "item_id": response.item_id,
            "name": response.name,
            "new_stock": response.quantity,
            "quantity_delta": quantity_delta,
            "unit_price": response.unit_price,
            "category": response.category,
            "success": response.success,
            "message": response.message,
        }

    def stream_analytics(
        self, metric_name: str, count: int = 5
    ) -> Iterator[Dict[str, Any]]:
        """
        Appel Server Streaming vers StreamAnalytics via gRPC.
        Consomme le flux HTTP/2 et émet les événements un par un sous forme de dictionnaires.
        """
        self._ensure_connected()
        req = inventory_pb2.AnalyticsRequest(metric_name=metric_name, count=count)
        stream_response = self.stub.StreamAnalytics(req, timeout=self.timeout)

        for event in stream_response:
            yield {
                "metric_name": event.metric_name,
                "value": event.value,
                "timestamp": event.timestamp,
                "server_id": event.server_id,
            }

    def close(self):
        """Ferme proprement le canal gRPC."""
        if self.channel is not None:
            self.channel.close()
            self.channel = None
            self.stub = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
