"""
Démarrage des trois serveurs du laboratoire autour d'UN SEUL service métier.

Usage en code (tout dans le même processus, ports libres choisis par l'OS) :

    with LabServers() as lab:
        client = lab.custom_client()
        print(client.calculate_factorial(n=5))

Usage en terminal (vrai client/serveur dans deux processus séparés) :

    python main.py --serve custom --port 5000     # terminal 1
    python main.py --call custom calculate_factorial n=5 --port 5000   # terminal 2
"""

import logging
import time
from typing import Any, Optional

# Le serveur HTTP de développement (werkzeug) journalise chaque requête :
# on le rend silencieux pour garder des démonstrations lisibles.
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from business.inventory_service import InventoryService
from grpc_impl.grpc_client import InventoryGRPCClient
from grpc_impl.grpc_server import InventoryGRPCServer
from rest.rest_client import RestClient
from rest.rest_server import RestServer
from rpc_core import RPCClient, RPCServer

# Méthodes métier exposées par le Custom RPC (table blanche du dispatcher)
EXPOSED_METHODS = [
    "calculate_factorial",
    "get_product_details",
    "update_stock",
    "stream_analytics",
]


def build_custom_server(
    service: InventoryService,
    host: str = "127.0.0.1",
    port: int = 0,
    tracer: Optional[Any] = None,
    failure_simulator: Optional[Any] = None,
) -> RPCServer:
    server = RPCServer(host=host, port=port, tracer=tracer, failure_simulator=failure_simulator)
    server.register_service(service, EXPOSED_METHODS)
    # Même nom, version flux : client.stream("stream_analytics", ...)
    server.register_stream("stream_analytics", service.stream_analytics_iter)
    return server


class LabServers:
    """Démarre Custom RPC + gRPC + REST partageant la même instance de service métier."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        custom_port: int = 0,
        grpc_port: int = 0,
        rest_port: int = 0,
        tracer: Optional[Any] = None,
        failure_simulator: Optional[Any] = None,
        protocols: Optional[list] = None,
    ):
        self.host = host
        self.service = InventoryService()
        self.tracer = tracer
        self.failure_simulator = failure_simulator
        self.protocols = protocols or ["custom", "grpc", "rest"]
        self.custom = build_custom_server(self.service, host, custom_port, tracer, failure_simulator) \
            if "custom" in self.protocols else None
        self.grpc = InventoryGRPCServer(host=host, port=grpc_port, service=self.service,
                                        failure_simulator=failure_simulator) \
            if "grpc" in self.protocols else None
        self.rest = RestServer(host=host, port=rest_port, service=self.service,
                               failure_simulator=failure_simulator) \
            if "rest" in self.protocols else None
        self.custom_port = self.grpc_port = self.rest_port = None

    # Cycle de vie ------------------------------------------------------
    def start(self) -> "LabServers":
        if self.custom:
            self.custom.start(threaded=True)
            self.custom_port = self.custom.port
        if self.grpc:
            self.grpc_port = self.grpc.start()
        if self.rest:
            self.rest_port = self.rest.start(threaded=True)
        return self

    def stop(self) -> None:
        if self.custom:
            self.custom.stop()
        if self.grpc:
            self.grpc.stop(grace=0.2)
        if self.rest:
            self.rest.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    # Fabriques de clients ---------------------------------------------
    def custom_client(self, timeout: float = 5.0, persistent: bool = False, tracer=None) -> RPCClient:
        return RPCClient(host=self.host, port=self.custom_port, timeout=timeout,
                         persistent=persistent, tracer=tracer)

    def grpc_client(self, timeout: float = 5.0, interceptors=None) -> InventoryGRPCClient:
        client = InventoryGRPCClient(host=self.host, port=self.grpc_port, timeout=timeout,
                                     interceptors=interceptors)
        client.connect()
        return client

    def rest_client(self, timeout: float = 5.0) -> RestClient:
        return RestClient(base_url=f"http://{self.host}:{self.rest_port}", timeout=timeout)

    def describe(self) -> str:
        parts = []
        if self.custom:
            parts.append(f"Custom RPC  tcp://{self.host}:{self.custom_port}")
        if self.grpc:
            parts.append(f"gRPC        {self.host}:{self.grpc_port} (HTTP/2)")
        if self.rest:
            parts.append(f"REST        http://{self.host}:{self.rest_port}")
        return "\n".join(parts)


def serve_forever(protocol: str, host: str, port: int, trace: bool = False) -> None:
    """Lance un (ou tous les) serveur(s) au premier plan jusqu'à Ctrl+C.

    trace=True : le serveur Custom RPC affiche en direct ses étapes « Sous le capot ».
    """
    tracer = None
    if trace:
        from under_the_hood.tracer import RPCTracer
        tracer = RPCTracer(live=True)
    defaults = {"custom": 5000, "grpc": 50051, "rest": 5001}
    protocols = ["custom", "grpc", "rest"] if protocol == "all" else [protocol]
    ports = {p: (port if (port and protocol != "all") else defaults[p]) for p in protocols}
    lab = LabServers(host=host, protocols=protocols, tracer=tracer,
                     custom_port=ports.get("custom", 0),
                     grpc_port=ports.get("grpc", 0),
                     rest_port=ports.get("rest", 0))
    lab.start()
    print("Serveurs démarrés (Ctrl+C pour arrêter) :")
    print(lab.describe())
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt des serveurs…")
    finally:
        lab.stop()
