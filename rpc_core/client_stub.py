"""
RPC Client Stub

Ce module fournit le client RPC Custom avec transparence d'appel.

Le stub permet d'appeler des méthodes distantes comme si elles étaient locales :
    client = RPCClient(host="localhost", port=5000)
    result = client.call("calculate_factorial", n=5)
    # ou grâce au stub dynamique :
    result = client.calculate_factorial(n=5)
"""

import socket
from typing import Any, Optional, Dict
from .serializer import RPCSerializer
from .transport import send_message, receive_message, TransportError, ConnectionClosedError


class RPCError(Exception):
    """
    Exception levée lorsque le serveur RPC retourne une erreur applicative ou protocolaire.

    Attributes:
        code: Code d'erreur (ex: "METHOD_NOT_FOUND", "INVALID_ARGS", "INTERNAL_ERROR")
        message: Message d'erreur explicatif
        data: Données de contexte ou traceback additionnel
    """

    def __init__(self, code: str, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"[{code}] {message}")


class RPCClient:
    """
    Client RPC Custom permettant des appels transparents vers un serveur distant.

    Architecture :
        CLIENT CALL (ex: client.calculate_factorial(n=5))
            ↓
        STUB (génération dynamique ou méthode .call())
            ↓
        SERIALIZATION (RPCSerializer -> JSON bytes UTF-8)
            ↓
        TRANSPORT (TCP Socket avec cadrage 4 octets)
            ↓
        NETWORK -> SERVER
    """

    def __init__(self, host: str = "localhost", port: int = 5000, timeout: float = 5.0):
        """
        Initialise le client RPC.

        Args:
            host: Adresse d'hôte du serveur RPC.
            port: Port d'écoute du serveur RPC.
            timeout: Timeout réseau en secondes pour la connexion et la réponse.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.serializer = RPCSerializer()

    def connect(self) -> socket.socket:
        """
        Établit une connexion TCP au serveur RPC avec timeout.

        Returns:
            socket.socket: Socket connectée et configurée.

        Raises:
            ConnectionError: Si la connexion est refusée ou impossible.
            TimeoutError: Si le délai de connexion est dépassé.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            return sock
        except socket.timeout as err:
            sock.close()
            raise TimeoutError(
                f"Timeout ({self.timeout}s) dépassé lors de la connexion à {self.host}:{self.port}"
            ) from err
        except (socket.error, OSError) as err:
            sock.close()
            raise ConnectionError(
                f"Impossible de se connecter au serveur RPC sur {self.host}:{self.port} : {err}"
            ) from err

    def _send_request(self, request_data: bytes) -> bytes:
        """
        Envoie une requête sérialisée et attend la réponse sérialisée.

        Args:
            request_data: Requête JSON encodée en bytes.

        Returns:
            bytes: Réponse JSON brute retournée par le serveur.

        Raises:
            ConnectionError: Si la connexion échoue ou est coupée.
            TimeoutError: Si le serveur ne répond pas dans le délai imparti.
        """
        sock = self.connect()
        try:
            send_message(sock, request_data)
            response_data = receive_message(sock)
            return response_data
        except (socket.timeout, TimeoutError) as err:
            raise TimeoutError(
                f"Timeout ({self.timeout}s) dépassé en attendant la réponse du serveur RPC."
            ) from err
        except ConnectionClosedError as err:
            raise ConnectionError(f"Le serveur RPC a fermé la connexion : {err}") from err
        except TransportError as err:
            raise ConnectionError(f"Erreur de communication réseau : {err}") from err
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def call(self, method: str, **kwargs) -> Any:
        """
        Exécute un appel distant synchrone.

        Args:
            method: Nom de la méthode distante.
            **kwargs: Arguments nommés à transmettre.

        Returns:
            Any: Résultat renvoyé par la méthode distante.

        Raises:
            RPCError: Si le serveur signale une erreur distante.
            ConnectionError: Si le transport échoue.
            TimeoutError: Si le timeout expire.
        """
        # 1. Sérialisation (Marshaling)
        req_bytes = self.serializer.serialize_request(method=method, args=kwargs)

        # 2. Transport réseau (Socket TCP)
        resp_bytes = self._send_request(req_bytes)

        # 3. Désérialisation (Unmarshaling)
        response = self.serializer.deserialize_response(resp_bytes)

        # 4. Vérification d'erreur applicative
        if response.get("error") is not None:
            err = response["error"]
            raise RPCError(
                code=err.get("code", "RPC_GENERIC_ERROR"),
                message=err.get("message", "Une erreur distante s'est produite"),
                data=err.get("data")
            )

        return response.get("result")

    def __getattr__(self, name: str):
        """
        Permet l'invocation dynamique transparente :
        client.calculate_factorial(n=5) équivaut à client.call("calculate_factorial", n=5)
        """
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' n'a pas d'attribut '{name}'")

        def dynamic_stub(**kwargs):
            return self.call(name, **kwargs)

        return dynamic_stub

    def close(self):
        """Ferme les ressources associées au client si applicable."""
        pass
