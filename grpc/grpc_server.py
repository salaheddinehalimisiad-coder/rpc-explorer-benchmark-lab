"""
Serveur gRPC pour le Service d'Inventaire et de Calcul

Expose le service métier via gRPC et HTTP/2 avec sérialisation Protobuf binaire.

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 04.
"""

from typing import Optional


class InventoryGRPCServer:
    """
    Serveur gRPC exposant les méthodes d'inventaire et de calcul.
    """

    def __init__(self, host: str = "[::]", port: int = 50051):
        self.host = host
        self.port = port
        self.server = None

    def start(self):
        """Démarre le serveur gRPC."""
        raise NotImplementedError("start() sera implémenté en Phase 04 après génération des stubs Protobuf")

    def stop(self, grace: Optional[float] = None):
        """Arrête le serveur gRPC proprement."""
        raise NotImplementedError("stop() sera implémenté en Phase 04")
