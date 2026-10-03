"""
Transparence de localisation : le même besoin métier codé de 4 façons.

    python main.py --transparency-demo

Le besoin : « retirer 1 unité du produit PROD-001 du stock ».
On montre le code que doit écrire l'APPELANT, puis on l'exécute réellement.
"""

import statistics
import time

import requests

from business.inventory_service import InventoryService
from cli.ui import explain, section, table, title
from lab.servers import LabServers
from protos import inventory_pb2, inventory_pb2_grpc

SNIPPETS = {
    "Appel local": '''service = InventoryService()
service.update_stock("PROD-001", -1)''',
    "Custom RPC": '''client = RPCClient(host, port)
client.update_stock(item_id="PROD-001", quantity_delta=-1)''',
    "gRPC": '''stub = InventoryRPCServiceStub(grpc.insecure_channel(addr))
stub.UpdateStock(UpdateStockRequest(item_id="PROD-001", quantity_delta=-1))''',
    "REST (requests brut)": '''resp = requests.post(f"{base}/api/products/PROD-001/stock",
                     json={"quantity_delta": -1}, timeout=5)
resp.raise_for_status()
data = resp.json()''',
}


def run_transparency_demo(iterations: int = 200):
    title("TRANSPARENCE DE LOCALISATION — le même appel métier, 4 styles de code")
    local = InventoryService()
    timings = {}
    with LabServers() as lab:
        import grpc
        rpc = lab.custom_client(persistent=True)
        channel = grpc.insecure_channel(f"127.0.0.1:{lab.grpc_port}")
        stub = inventory_pb2_grpc.InventoryRPCServiceStub(channel)
        base = f"http://127.0.0.1:{lab.rest_port}"
        http = requests.Session()

        def rest_call():
            resp = http.post(f"{base}/api/products/PROD-001/stock", json={"quantity_delta": -1}, timeout=5)
            resp.raise_for_status()
            return resp.json()

        runners = {
            "Appel local": lambda: local.update_stock("PROD-001", -1),
            "Custom RPC": lambda: rpc.update_stock(item_id="PROD-001", quantity_delta=-1),
            "gRPC": lambda: stub.UpdateStock(inventory_pb2.UpdateStockRequest(item_id="PROD-001",
                                                                                quantity_delta=-1)),
            "REST (requests brut)": rest_call,
        }
        for name, code in SNIPPETS.items():
            section(name)
            print("  " + code.replace("\n", "\n  "))
            fn = runners[name]
            # On remet du stock pour ne jamais tomber à 0 pendant la mesure
            lab.service.update_stock("PROD-001", iterations)
            local.update_stock("PROD-001", iterations)
            fn()  # échauffement
            samples = []
            for _ in range(iterations):
                t0 = time.perf_counter()
                fn()
                samples.append((time.perf_counter() - t0) * 1000)
            timings[name] = statistics.median(samples)
            print(f"  → exécuté {iterations} fois, médiane {timings[name]:.4f} ms par appel")
        rpc.close(); channel.close(); http.close()

    section("Comparaison")
    base_t = timings["Appel local"]
    print(table(["Style", "Médiane / appel", "× appel local"],
                [(k, f"{v:.4f} ms", f"×{v / base_t:,.0f}") for k, v in timings.items()]))
    explain("""
AVANTAGE du RPC : le code Custom RPC ressemble presque mot pour mot à l'appel local
(c'est le stub qui cache le réseau). En REST, l'appelant manipule lui-même URL,
verbe HTTP, JSON et codes de statut.
PIÈGE : cette ressemblance est trompeuse. Même en localhost, l'appel distant est
des dizaines à des centaines de fois plus lent, et il peut échouer (voir --simulate-failures).""")
    return timings
