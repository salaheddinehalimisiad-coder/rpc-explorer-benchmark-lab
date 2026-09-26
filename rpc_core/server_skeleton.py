"""
RPC Server Skeleton & Dispatcher

Ce module fournit le serveur RPC Custom avec dispatcher et skeleton.

Le serveur écoute sur un socket TCP et dispatche les requêtes vers les fonctions métier autorisées.

Architecture:
    NETWORK
        ↓
    TCP SOCKET
        ↓
    RECEIVER (avec cadrage par longueur)
        ↓
    DESERIALIZER (RPCSerializer)
        ↓
    DISPATCHER (validation + vérification table blanche)
        ↓
    BUSINESS FUNCTION
        ↓
    SERIALIZER (RPCSerializer)
        ↓
    RESPONSE
"""

import socket
import threading
import logging
from typing import Dict, Callable, Any, Optional
from .serializer import RPCSerializer
from .transport import send_message, receive_message, TransportError, ConnectionClosedError

logger = logging.getLogger("RPCServer")


class RPCMethodNotFoundError(Exception):
    """Exception levée quand une méthode RPC n'existe pas dans la table blanche."""
    pass


class RPCInvalidArgsError(Exception):
    """Exception levée quand les arguments fournis à la méthode sont invalides."""
    pass


class RPCServerError(Exception):
    """Exception levée en cas d'erreur interne du serveur RPC."""
    pass


class RPCServer:
    """
    Serveur RPC Custom avec dispatcher et skeleton multi-threadé.

    Responsabilités:
    - Écouter sur un socket TCP
    - Recevoir les requêtes RPC cadrées
    - Désérialiser les requêtes JSON
    - Dispatcher vers les fonctions autorisées (sécurité par table blanche)
    - Exécuter la fonction métier en isolant les exceptions
    - Sérialiser la réponse ou l'erreur structurée
    - Renvoyer la réponse cadrée au client
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        failure_simulator: Optional[Any] = None,
    ):
        """
        Initialise le serveur RPC.

        Args:
            host: Adresse d'écoute (par défaut '127.0.0.1').
            port: Port d'écoute (si 0, un port libre sera alloué dynamiquement).
            failure_simulator: Simulateur d'anomalies optionnel (Phase 07).
        """
        self.host = host
        self.port = port
        self.failure_simulator = failure_simulator
        self.methods: Dict[str, Callable] = {}
        self.serializer = RPCSerializer()
        self.running = False
        self._server_socket: Optional[socket.socket] = None
        self._listener_thread: Optional[threading.Thread] = None

    def register_method(self, name: str, function: Callable):
        """
        Enregistre une méthode dans la table blanche des fonctions exécutables.

        Args:
            name: Nom d'exposition de la méthode (tel qu'appelé par le client).
            function: Callable Python correspondant.
        """
        if not name or not isinstance(name, str):
            raise ValueError("Le nom de méthode doit être une chaîne non vide.")
        if not callable(function):
            raise TypeError("Le second argument doit être un callable (fonction ou méthode).")

        self.methods[name] = function
        logger.debug("Méthode RPC enregistrée : %s", name)

    def start(self, threaded: bool = True):
        """
        Démarre le serveur RPC.

        Args:
            threaded: Si True, lance la boucle d'écoute dans un thread d'arrière-plan.
        """
        if self.running:
            return

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        
        # Récupération du port réel (très utile si port=0)
        self.port = self._server_socket.getsockname()[1]
        self._server_socket.listen(128)
        self.running = True

        logger.info("Serveur RPC démarré sur %s:%d", self.host, self.port)

        if threaded:
            self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listener_thread.start()
        else:
            self._listen_loop()

    def _listen_loop(self):
        """Boucle principale d'acceptation des connexions clients."""
        while self.running:
            try:
                client_sock, addr = self._server_socket.accept()
            except (socket.error, OSError):
                # Socket fermé lors de l'arrêt
                break

            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_sock, addr),
                daemon=True
            )
            client_thread.start()

    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """
        Traite une connexion client en continu jusqu'à fermeture.

        Args:
            client_socket: Socket connectée avec le client.
            address: Tuple (ip, port) du client.
        """
        try:
            while self.running:
                try:
                    request_bytes = receive_message(client_socket)
                except (ConnectionClosedError, TransportError):
                    break

                if self.failure_simulator is not None:
                    try:
                        self.failure_simulator.apply_pre_execution_hooks()
                    except ConnectionAbortedError:
                        break

                try:
                    request = self.serializer.deserialize_request(request_bytes)
                    response_dict = self._dispatch(request)
                except ValueError as val_err:
                    response_dict = {
                        "id": "unknown",
                        "result": None,
                        "error": {
                            "code": "INVALID_REQUEST_FORMAT",
                            "message": str(val_err),
                            "data": {}
                        },
                        "metadata": {}
                    }
                except Exception as ex:
                    response_dict = {
                        "id": "unknown",
                        "result": None,
                        "error": {
                            "code": "SERVER_INTERNAL_ERROR",
                            "message": str(ex),
                            "data": {}
                        },
                        "metadata": {}
                    }

                resp_bytes = self.serializer.serialize_response(
                    request_id=response_dict["id"],
                    result=response_dict.get("result"),
                    error=response_dict.get("error"),
                    metadata=response_dict.get("metadata")
                )
                try:
                    send_message(client_socket, resp_bytes)
                except TransportError:
                    break
        finally:
            try:
                client_socket.close()
            except OSError:
                pass

    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatche une requête validée vers la fonction métier autorisée.

        Args:
            request: Dictionnaire de requête avec clés 'id', 'method', 'args'.

        Returns:
            dict: Dictionnaire de réponse avec 'id', 'result', 'error', 'metadata'.
        """
        req_id = request.get("id", "unknown")
        method_name = request.get("method")
        args = request.get("args", {})

        # 1. Contrôle par table blanche
        if method_name not in self.methods:
            return {
                "id": req_id,
                "result": None,
                "error": {
                    "code": "METHOD_NOT_FOUND",
                    "message": f"La méthode '{method_name}' n'est pas autorisée ou n'existe pas.",
                    "data": {"available_methods": list(self.methods.keys())}
                },
                "metadata": {"status": "ERROR"}
            }

        func = self.methods[method_name]

        # 2. Exécution protégée
        try:
            result = func(**args)
            return {
                "id": req_id,
                "result": result,
                "error": None,
                "metadata": {"status": "SUCCESS"}
            }
        except TypeError as type_err:
            return {
                "id": req_id,
                "result": None,
                "error": {
                    "code": "INVALID_ARGS",
                    "message": f"Arguments invalides pour '{method_name}' : {type_err}",
                    "data": {"provided_args": list(args.keys())}
                },
                "metadata": {"status": "ERROR"}
            }
        except Exception as exc:
            return {
                "id": req_id,
                "result": None,
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": str(exc),
                    "data": {"exception_type": type(exc).__name__}
                },
                "metadata": {"status": "ERROR"}
            }

    def stop(self):
        """Arrête le serveur RPC proprement et libère les sockets."""
        self.running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=1.0)
