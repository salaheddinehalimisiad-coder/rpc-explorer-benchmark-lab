"""
Serveur gRPC pour le Service d'Inventaire et de Calcul

Expose la logique métier (InventoryService) via gRPC et HTTP/2
avec sérialisation binaire Protobuf.
Conforme au contrat IDL protos/inventory.proto et au cahier des charges officiel.
"""

import time
import datetime
from concurrent import futures
from typing import Optional, Iterator

import grpc

from business.inventory_service import InventoryService
from protos import inventory_pb2
from protos import inventory_pb2_grpc


class InventoryServicer(inventory_pb2_grpc.InventoryRPCServiceServicer):
    """
    Servicer gRPC implémentant l'interface définie dans inventory.proto.
    Délègue intégralement l'exécution métier à l'instance InventoryService injectée.
    Adapte les structures de données métier vers les messages Protobuf.
    """

    def __init__(
        self,
        service: Optional[InventoryService] = None,
        server_id: str = "grpc_server_01",
    ):
        self._service = service if service is not None else InventoryService()
        self.server_id = server_id

    @property
    def service(self) -> InventoryService:
        """Accès au service métier sous-jacent."""
        return self._service

    def CalculateFactorial(
        self, request: inventory_pb2.FactorialRequest, context: grpc.ServicerContext
    ) -> inventory_pb2.FactorialResponse:
        """
        Calcul de factorielle via gRPC (appel unaire CPU-bound).
        Gère les contraintes du contrat IDL (int64) et les validations métier.
        """
        n = request.n
        # Validation des bornes métier et de la capacité du type int64 Protobuf
        # 20! = 2_432_902_008_176_640_000 (tient dans int64 signé, max 9.22e18)
        # 21! = 51_090_942_171_709_440_000 (dépassement int64)
        if n < 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"L'argument n doit être positif ou nul (reçu: {n}).",
            )
        if n > 20:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"L'argument n={n} dépasse la capacité du type int64 Protobuf (n <= 20).",
            )

        start_time = time.perf_counter()
        try:
            result = self._service.calculate_factorial(n)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        except Exception as exc:
            context.abort(grpc.StatusCode.INTERNAL, f"Erreur interne: {exc}")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return inventory_pb2.FactorialResponse(
            result=result,
            execution_time_ms=elapsed_ms,
        )

    def GetProductDetails(
        self, request: inventory_pb2.ProductRequest, context: grpc.ServicerContext
    ) -> inventory_pb2.ProductResponse:
        """
        Consultation des détails d'un produit (appel unaire).
        Renvoie NOT_FOUND si le produit est inconnu.
        """
        item_id = request.item_id
        if not item_id or not item_id.strip():
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "L'identifiant produit 'item_id' ne peut pas être vide.",
            )

        try:
            prod = self._service.get_product_details(item_id)
            return inventory_pb2.ProductResponse(
                item_id=prod["item_id"],
                name=prod["name"],
                quantity=int(prod["stock"]),
                unit_price=float(prod["price"]),
                category=str(prod["category"]),
                success=True,
                message="Produit trouvé.",
            )
        except ValueError as exc:
            err_msg = str(exc)
            if "introuvable" in err_msg.lower() or "non trouvé" in err_msg.lower():
                context.abort(grpc.StatusCode.NOT_FOUND, err_msg)
            else:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, err_msg)
        except Exception as exc:
            context.abort(grpc.StatusCode.INTERNAL, f"Erreur interne: {exc}")

    def UpdateStock(
        self, request: inventory_pb2.UpdateStockRequest, context: grpc.ServicerContext
    ) -> inventory_pb2.ProductResponse:
        """
        Mise à jour du stock d'un produit (appel unaire mutation).
        Renvoie NOT_FOUND si le produit n'existe pas,
        ou FAILED_PRECONDITION si le stock est insuffisant.
        """
        item_id = request.item_id
        delta = request.quantity_delta

        if not item_id or not item_id.strip():
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "L'identifiant produit 'item_id' ne peut pas être vide.",
            )

        try:
            result = self._service.update_stock(item_id, delta)
            # Récupérer les détails complets pour la réponse IDL
            details = self._service.get_product_details(item_id)
            return inventory_pb2.ProductResponse(
                item_id=result["item_id"],
                name=details["name"],
                quantity=int(result["new_stock"]),
                unit_price=float(details["price"]),
                category=str(details["category"]),
                success=True,
                message=f"Stock mis à jour pour '{item_id}' : nouveau stock = {result['new_stock']}.",
            )
        except ValueError as exc:
            err_msg = str(exc)
            if "introuvable" in err_msg.lower() or "non trouvé" in err_msg.lower():
                context.abort(grpc.StatusCode.NOT_FOUND, err_msg)
            elif "insuffisant" in err_msg.lower():
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, err_msg)
            else:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, err_msg)
        except Exception as exc:
            context.abort(grpc.StatusCode.INTERNAL, f"Erreur interne: {exc}")

    def StreamAnalytics(
        self, request: inventory_pb2.AnalyticsRequest, context: grpc.ServicerContext
    ) -> Iterator[inventory_pb2.AnalyticsResponse]:
        """
        Flux d'analyses et métriques en temps réel (vrai Server Streaming gRPC).
        Émet les événements un par un sur le flux HTTP/2.
        """
        metric_name = request.metric_name
        count = request.count

        if count <= 0:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"Le nombre d'événements doit être strictement positif (reçu: {count}).",
            )

        try:
            events = self._service.stream_analytics(metric_name, count)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
            return

        for ev in events:
            if not context.is_active():
                break

            # Conversion du timestamp ISO en millisecondes entières (int64)
            ts_str = ev.get("timestamp", "")
            try:
                dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ts_int = int(dt.timestamp() * 1000)
            except Exception:
                ts_int = int(time.time() * 1000)

            metric_key = ev.get("metric", metric_name)
            yield inventory_pb2.AnalyticsResponse(
                metric_name=metric_key,
                value=float(ev["value"]),
                timestamp=ts_int,
                server_id=self.server_id,
            )


class InventoryGRPCServer:
    """
    Gestionnaire du cycle de vie du serveur gRPC (démarrage, arrêt, configuration de port).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        service: Optional[InventoryService] = None,
        max_workers: int = 10,
        server_id: str = "grpc_server_01",
    ):
        self.host = host
        self.port = port
        self.service = service if service is not None else InventoryService()
        self.max_workers = max_workers
        self.server_id = server_id
        self.server: Optional[grpc.Server] = None
        self.bound_port: int = 0
        self.is_running: bool = False
        self._servicer = InventoryServicer(self.service, server_id=self.server_id)

    @property
    def servicer(self) -> InventoryServicer:
        """Accès au servicer gRPC."""
        return self._servicer

    def start(self) -> int:
        """
        Démarre le serveur gRPC.
        Si port=0, un port éphémère libre est automatiquement alloué.
        Retourne le port d'écoute effectif.
        """
        if self.is_running:
            return self.bound_port

        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers)
        )
        inventory_pb2_grpc.add_InventoryRPCServiceServicer_to_server(
            self._servicer, self.server
        )
        self.bound_port = self.server.add_insecure_port(f"{self.host}:{self.port}")
        if self.bound_port == 0:
            raise RuntimeError(f"Impossible de lier le serveur gRPC sur {self.host}:{self.port}")

        self.server.start()
        self.is_running = True
        return self.bound_port

    def stop(self, grace: Optional[float] = 0.5):
        """
        Arrête proprement le serveur gRPC avec délai de grâce facultatif.
        """
        if self.server and self.is_running:
            event = self.server.stop(grace=grace)
            if event is not None:
                timeout = (grace or 0.0) + 2.0
                event.wait(timeout=timeout)
            self.is_running = False
            self.server = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop(grace=0.5)
