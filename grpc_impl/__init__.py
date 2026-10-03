"""
Implémentation gRPC du service d'inventaire (serveur + client).

NB : ce package s'appelle `grpc_impl` (et non `grpc`) pour ne pas masquer
la bibliothèque officielle `grpc` (grpcio) installée via pip.
"""

from .grpc_server import InventoryGRPCServer, InventoryServicer
from .grpc_client import InventoryGRPCClient

__all__ = ["InventoryGRPCServer", "InventoryServicer", "InventoryGRPCClient"]
