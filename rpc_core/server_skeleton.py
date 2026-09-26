"""
RPC Server Skeleton

Ce module fournit le serveur RPC Custom avec dispatcher et skeleton.

Le serveur écoute sur un socket TCP et dispatche les appels vers les fonctions métier.

Architecture:
    NETWORK
        ↓
    TCP SOCKET
        ↓
    RECEIVER
        ↓
    DESERIALIZER
        ↓
    DISPATCHER (validation + lookup)
        ↓
    BUSINESS FUNCTION
        ↓
    SERIALIZER
        ↓
    RESPONSE

STATUT: PLACEHOLDER — Implémentation prévue en Phase 02
"""

import socket
import threading
from typing import Dict, Callable, Any, Optional
from .serializer import RPCSerializer


class RPCServer:
    """
    Serveur RPC Custom avec dispatcher et skeleton.

    Responsabilités:
    - Écouter sur un socket TCP
    - Recevoir les requêtes RPC
    - Désérialiser les requêtes
    - Dispatcher vers les fonctions autorisées (table blanche)
    - Exécuter la fonction métier
    - Sérialiser la réponse
    - Envoyer la réponse

    Sécurité:
    - Seules les méthodes explicitement enregistrées peuvent être appelées
    - Pas d'exécution arbitraire de code

    Attributs:
        host: Adresse d'écoute
        port: Port d'écoute
        methods: Table blanche des méthodes autorisées
        serializer: Instance de RPCSerializer
    """

    def __init__(self, host: str = "localhost", port: int = 5000):
        """
        Initialise le serveur RPC.

        Args:
            host: Adresse d'écoute
            port: Port d'écoute
        """
        self.host = host
        self.port = port
        self.methods: Dict[str, Callable] = {}
        self.serializer = RPCSerializer()
        self.running = False

    def register_method(self, name: str, function: Callable):
        """
        Enregistre une méthode dans la table blanche.

        Args:
            name: Nom de la méthode (tel qu'appelé par le client)
            function: Fonction Python correspondante

        Example:
            >>> def calculate_factorial(n):
            ...     return factorial(n)
            >>> server = RPCServer()
            >>> server.register_method("calculate_factorial", calculate_factorial)
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("register_method sera implémenté en Phase 02")

    def start(self):
        """
        Démarre le serveur RPC.

        Le serveur écoute sur le socket TCP et accepte les connexions.
        Chaque connexion est traitée dans un thread séparé.

        Raises:
            OSError: Si le port est déjà utilisé
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("start sera implémenté en Phase 02")

    def stop(self):
        """
        Arrête le serveur RPC proprement.
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("stop sera implémenté en Phase 02")

    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """
        Traite une connexion client.

        Args:
            client_socket: Socket de la connexion client
            address: Adresse du client (host, port)
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("_handle_client sera implémenté en Phase 02")

    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatche une requête vers la fonction métier appropriée.

        Étapes:
        1. Valider la requête
        2. Vérifier que la méthode existe dans la table blanche
        3. Extraire les arguments
        4. Appeler la fonction métier
        5. Construire la réponse

        Args:
            request: Requête désérialisée

        Returns:
            dict: Réponse sérialisable

        Raises:
            RPCMethodNotFoundError: Si la méthode n'existe pas
            RPCInvalidArgsError: Si les arguments sont invalides
        """
        # TODO: Implémenter en Phase 02
        raise NotImplementedError("_dispatch sera implémenté en Phase 02")


class RPCMethodNotFoundError(Exception):
    """Exception levée quand une méthode RPC n'existe pas."""
    pass


class RPCInvalidArgsError(Exception):
    """Exception levée quand les arguments RPC sont invalides."""
    pass


class RPCServerError(Exception):
    """Exception levée en cas d'erreur serveur."""
    pass
