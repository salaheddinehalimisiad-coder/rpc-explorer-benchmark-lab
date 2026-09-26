"""
RPC Client Stub

Ce module fournit le client RPC Custom avec transparence d'appel.

Le stub permet d'appeler des méthodes distantes comme si elles étaient locales:
    client = RPCClient(host="localhost", port=5000)
    result = client.call("calculate_factorial", n=5)

STATUT: PLACEHOLDER — Implémentation prévue en Phase 02
"""

import socket
from typing import Any, Optional, Dict
from .serializer import RPCSerializer


class RPCClient:
    """
    Client RPC Custom permettant des appels transparents vers un serveur distant.

    Architecture:
        CLIENT CALL
            ↓
        STUB (ce module)
            ↓
        SERIALIZATION (RPCSerializer)
            ↓
        TRANSPORT (TCP Socket)
            ↓
        NETWORK → SERVER

    Attributs:
        host: Adresse du serveur RPC
        port: Port du serveur RPC
        timeout: Timeout des appels RPC (secondes)
        serializer: Instance de RPCSerializer
    """

    def __init__(self, host: str = "localhost", port: int = 5000, timeout: float = 5.0):
        """
        Initialise le client RPC.

        Args:
            host: Adresse du serveur
            port: Port du serveur
            timeout: Timeout pour les appels RPC (secondes)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.serializer = RPCSerializer()

    def call(self, method: str, **kwargs) -> Any:
        """
        Appelle une méthode distante via RPC.

        Cette méthode fournit la transparence d'appel:
        L'utilisateur appelle client.call("method", arg1=val1) comme une fonction locale,
        mais derrière:
            1. Sérialisation de la requête
            2. Envoi via socket
            3. Attente de la réponse
            4. Désérialisation
            5. Retour du résultat

        Args:
            method: Nom de la méthode à appeler
            **kwargs: Arguments de la méthode

        Returns:
            Any: Résultat de l'appel distant

        Raises:
            ConnectionError: Si connexion au serveur échoue
            TimeoutError: Si le serveur ne répond pas dans le délai
            RPCError: Si le serveur retourne une erreur

        Example:
            >>> client = RPCClient()
            >>> result = client.call("calculate_factorial", n=5)
            >>> print(result)
            120
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("call sera implémenté en Phase 02")

    def _send_request(self, request_data: bytes) -> bytes:
        """
        Envoie une requête RPC au serveur et attend la réponse.

        Args:
            request_data: Données sérialisées de la requête

        Returns:
            bytes: Réponse sérialisée du serveur

        Raises:
            ConnectionError: Si la connexion échoue
            TimeoutError: Si timeout atteint
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("_send_request sera implémenté en Phase 02")

    def connect(self) -> socket.socket:
        """
        Établit une connexion TCP au serveur RPC.

        Returns:
            socket.socket: Socket connecté

        Raises:
            ConnectionError: Si la connexion échoue
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("connect sera implémenté en Phase 02")

    def close(self):
        """
        Ferme la connexion au serveur (si persistante).
        """
        # TODO: Implémenter en Phase 02 si nécessaire
        pass


class RPCError(Exception):
    """
    Exception levée lorsque le serveur RPC retourne une erreur.

    Attributes:
        code: Code d'erreur (ex: "METHOD_NOT_FOUND", "INVALID_ARGS")
        message: Message d'erreur
        data: Données additionnelles
    """

    def __init__(self, code: str, message: str, data: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"[{code}] {message}")
