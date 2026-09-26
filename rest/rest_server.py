"""
Serveur REST HTTP / JSON

Expose les méthodes métier via des endpoints HTTP (GET, POST) pour comparaison expérimentale avec RPC.

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 05.
"""

from typing import Optional


class RestServer:
    """
    Serveur HTTP/REST encapsulant une application Flask pour exposer l'inventaire.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5001):
        self.host = host
        self.port = port
        self.app = None

    def start(self, threaded: bool = True):
        """Démarre le serveur REST."""
        raise NotImplementedError("start() sera implémenté en Phase 05")

    def stop(self):
        """Arrête le serveur REST."""
        raise NotImplementedError("stop() sera implémenté en Phase 05")
