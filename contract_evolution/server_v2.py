"""
Serveur gRPC VERSION 2 (contrat contract_evolution/protos_v2/inventory.proto).

Il tourne dans un PROCESSUS SÉPARÉ, comme un vrai déploiement : le contrat v2
déclare les mêmes noms Protobuf (package `inventory`) que la v1, ils ne peuvent
donc pas cohabiter dans le même interpréteur Python — ni sur le même serveur réel.

    python -m contract_evolution.server_v2 --port 50052

Au démarrage il affiche "READY <port>" (utilisé par la démo pour se synchroniser).
"""

import argparse
import sys
import time
from concurrent import futures

import grpc

from business.inventory_service import InventoryService
from contract_evolution.generated_v2 import inventory_pb2 as pb2
from contract_evolution.generated_v2 import inventory_pb2_grpc as pb2_grpc


class InventoryServicerV2(pb2_grpc.InventoryRPCServiceServicer):
    def __init__(self):
        self.service = InventoryService()

    def CalculateFactorial(self, request, context):
        # v2 : n est désormais une chaîne
        if not request.n:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "v2: le champ 'n' (string) est vide ou absent.")
        try:
            n = int(request.n)
            t0 = time.perf_counter()
            result = self.service.calculate_factorial(n)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"v2: {exc}")
        return pb2.FactorialResponse(result=result,
                                     execution_time_ms=(time.perf_counter() - t0) * 1000)

    def _product(self, item_id, message):
        p = self.service.get_product_details(item_id)
        return pb2.ProductResponse(
            item_id=p["item_id"], name=p["name"], quantity=int(p["stock"]),
            unit_price=float(p["price"]), category=p["category"], success=True,
            message=message, currency="EUR",
            stock_status="LOW" if p["stock"] < 30 else "OK",
        )

    def GetProductDetails(self, request, context):
        try:
            return self._product(request.product_id, "v2: produit trouvé.")
        except ValueError as exc:
            context.abort(grpc.StatusCode.NOT_FOUND, f"v2: {exc}")

    def UpdateStock(self, request, context):
        try:
            res = self.service.update_stock(request.item_id, request.quantity_delta)
            return self._product(
                request.item_id,
                f"v2: delta appliqué = {res['delta']} (raison: {request.reason or '—'}), "
                f"stock {res['previous_stock']} -> {res['new_stock']}.",
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"v2: {exc}")

    def StreamMetrics(self, request, context):
        for ev in self.service.stream_analytics(request.metric_name, request.count or 3):
            yield pb2.AnalyticsResponse(metric_name=request.metric_name,
                                        value=float(ev["value"]), server_id="grpc_server_v2")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serveur gRPC contrat v2 (démo)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_InventoryRPCServiceServicer_to_server(InventoryServicerV2(), server)
    port = server.add_insecure_port(f"{args.host}:{args.port}")
    server.start()
    print(f"READY {port}", flush=True)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
