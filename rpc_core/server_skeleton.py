"""
RPC Server Skeleton & Dispatcher

Ce module fournit le serveur RPC Custom avec dispatcher et skeleton.

Le serveur écoute sur un socket TCP et dispatche les requêtes vers les fonctions métier autorisées.

PROTOCOLE : JSON-RPC 2.0 (voir protocol.py) — requêtes, notifications, lots,
codes d'erreur normalisés, plus l'extension de flux "rpc.stream".
"""

import inspect
import socket
import threading
import logging
import time
from typing import Dict, Callable, Any, Optional
from . import protocol
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
        tracer: Optional[Any] = None,
    ):
        """
        Initialise le serveur RPC.

        Args:
            host: Adresse d'écoute (par défaut '127.0.0.1').
            port: Port d'écoute (si 0, un port libre sera alloué dynamiquement).
            failure_simulator: Simulateur d'anomalies optionnel (Phase 07).
            tracer: RPCTracer optionnel (mode "Sous le capot").
        """
        self.host = host
        self.port = port
        self.failure_simulator = failure_simulator
        self.tracer = tracer
        self.methods: Dict[str, Callable] = {}
        self.stream_methods: Dict[str, Callable] = {}
        self.serializer = RPCSerializer()
        self.running = False
        self._server_socket: Optional[socket.socket] = None
        self._listener_thread: Optional[threading.Thread] = None
        # Connexions clientes actives : fermées par stop() pour qu'un arrêt
        # du serveur coupe réellement les clients déjà connectés.
        self._client_sockets: set = set()
        self._clients_lock = threading.Lock()

    def _trace(self, step: str, call_id: Optional[str], **details):
        if self.tracer is not None:
            self.tracer.record_step(step, details, call_id=call_id, side="server")

    def register_service(self, service: Any, method_names: Any) -> None:
        """Enregistre plusieurs méthodes d'un objet métier dans la table blanche."""
        for name in method_names:
            self.register_method(name, getattr(service, name))

    def register_stream(self, name: str, generator_function: Callable):
        """
        Enregistre une méthode de STREAMING (elle doit retourner un itérateur).

        Le même nom peut aussi être enregistré avec register_method() : le client
        choisit alors entre réponse unique (call) et flux (stream).
        """
        if not name or not isinstance(name, str):
            raise ValueError("Le nom de méthode doit être une chaîne non vide.")
        if not callable(generator_function):
            raise TypeError("Le second argument doit être un callable retournant un itérateur.")
        self.stream_methods[name] = generator_function

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

            with self._clients_lock:
                self._client_sockets.add(client_sock)
            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_sock, addr),
                daemon=True
            )
            client_thread.start()

    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """
        Traite une connexion client en continu jusqu'à fermeture.

        Chaque trame reçue contient UN message JSON-RPC 2.0 : une requête, une
        notification (sans "id", donc sans réponse), un lot (tableau de
        requêtes) ou une requête de flux "rpc.stream".
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
                    msg = protocol.decode(request_bytes)
                except protocol.ProtocolError as err:
                    if not self._reply(client_socket, protocol.make_error(None, err.name, str(err))):
                        break
                    continue

                # Lot (batch) : une réponse par requête, aucune pour les notifications
                if isinstance(msg, list):
                    if not msg:
                        reply = protocol.make_error(None, "INVALID_REQUEST", "Un lot ne peut pas être vide.")
                    else:
                        responses = [r for r in (self._process(m, address, len(request_bytes), batch=True)
                                                 for m in msg) if r is not None]
                        reply = responses or None
                    if reply is not None and not self._reply(client_socket, reply):
                        break
                    continue

                # Flux (extension rpc.stream)
                if isinstance(msg, dict) and msg.get("method") == protocol.STREAM_METHOD and "id" in msg:
                    try:
                        protocol.validate_request(msg)
                    except protocol.ProtocolError as err:
                        if not self._reply(client_socket, protocol.make_error(msg.get("id"), err.name, str(err))):
                            break
                        continue
                    if not self._dispatch_stream(client_socket, msg, address, len(request_bytes)):
                        break
                    continue

                response = self._process(msg, address, len(request_bytes))
                if response is not None and not self._reply(client_socket, response):
                    break
        finally:
            with self._clients_lock:
                self._client_sockets.discard(client_socket)
            try:
                client_socket.close()
            except OSError:
                pass

    def _reply(self, sock: socket.socket, message: Any) -> bool:
        """Sérialise et envoie une réponse (ou un lot de réponses). False si la connexion est perdue."""
        data = protocol.encode(message)
        trace_id = message.get("id") if isinstance(message, dict) else "lot"
        self._trace("SERIALIZE_RESPONSE + TRANSPORT_REPLY", trace_id,
                    payload=data, taille=f"{len(data)} octets")
        try:
            send_message(sock, data)
            return True
        except TransportError:
            return False

    def _process(self, msg: Any, address: tuple, size: int, batch: bool = False) -> Optional[Dict[str, Any]]:
        """Valide puis exécute UNE requête. Retourne la réponse, ou None pour une notification."""
        try:
            protocol.validate_request(msg)
        except protocol.ProtocolError as err:
            rid = msg.get("id") if isinstance(msg, dict) else None
            return protocol.make_error(rid if isinstance(rid, (str, int)) else None, err.name, str(err))
        req_id = msg.get("id")
        self._trace("SERVER_RECEIVE + DESERIALIZE", req_id,
                    depuis=f"{address[0]}:{address[1]}", octets_recus=size,
                    message_decode={"method": msg["method"], "params": msg.get("params")})
        if batch and msg["method"] == protocol.STREAM_METHOD:
            return protocol.make_error(req_id, "INVALID_REQUEST", "rpc.stream n'est pas autorisé dans un lot.")
        response = self._dispatch(msg)
        if protocol.is_notification(msg):
            self._trace("NOTIFICATION (aucune réponse)", None, methode=msg["method"])
            return None
        return response

    def _check_args(self, func: Callable, args: list, kwargs: Dict[str, Any]) -> Optional[str]:
        """Vérifie que les paramètres correspondent à la signature AVANT d'exécuter."""
        try:
            inspect.signature(func).bind(*args, **kwargs)
            return None
        except TypeError as err:
            return str(err)
        except ValueError:  # signature introuvable (callable natif) : on laisse l'appel décider
            return None

    def _dispatch_stream(self, sock: socket.socket, request: Dict[str, Any], address: tuple, size: int) -> bool:
        """
        Exécute une méthode de streaming : une notification "rpc.stream.item" par
        élément produit, puis UNE réponse finale à la requête.

        Returns:
            False si la connexion est perdue (le client est parti) : on arrête
            alors l'itérateur au lieu de produire des données pour personne.
        """
        req_id = request["id"]
        params = request.get("params") or {}
        method_name = params.get("method") if isinstance(params, dict) else None
        inner = params.get("params") if isinstance(params, dict) else None
        self._trace("SERVER_RECEIVE + DESERIALIZE", req_id, depuis=f"{address[0]}:{address[1]}",
                    octets_recus=size, message_decode={"method": "rpc.stream", "params": params})
        self._trace("DISPATCH (table blanche des flux)", req_id, methode=method_name,
                    autorisee=method_name in self.stream_methods)
        if method_name not in self.stream_methods:
            return self._reply(sock, protocol.make_error(
                req_id, "STREAM_NOT_SUPPORTED",
                f"La méthode '{method_name}' n'est pas disponible en streaming.",
                {"stream_methods": list(self.stream_methods.keys())}))
        func = self.stream_methods[method_name]
        args, kwargs = protocol.split_params(inner)
        problem = self._check_args(func, args, kwargs)
        if problem:
            return self._reply(sock, protocol.make_error(
                req_id, "INVALID_ARGS", f"Arguments invalides pour '{method_name}' : {problem}",
                {"provided_args": list(kwargs.keys()) or len(args)}))
        try:
            iterator = iter(func(*args, **kwargs))
        except Exception as exc:
            return self._reply(sock, protocol.make_error(
                req_id, "EXECUTION_ERROR", str(exc), {"exception_type": type(exc).__name__}))

        count = 0
        try:
            for item in iterator:
                count += 1
                self._trace(f"STREAM_SEND trame n°{count}", req_id, element=item)
                try:
                    send_message(sock, protocol.encode(protocol.make_stream_item(req_id, count, item)))
                except TransportError:
                    self._trace("STREAM_ABORT (client parti)", req_id, trames_envoyees=count - 1)
                    return False
        except Exception as exc:
            return self._reply(sock, protocol.make_error(
                req_id, "EXECUTION_ERROR", str(exc),
                {"exception_type": type(exc).__name__, "items_sent": count}))
        finally:
            close = getattr(iterator, "close", None)
            if close:
                close()
        self._trace("STREAM_END", req_id, trames_envoyees=count)
        return self._reply(sock, protocol.make_result(req_id, {"count": count}))

    def _dispatch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatche une requête JSON-RPC validée vers la fonction métier autorisée.

        Returns:
            dict: réponse JSON-RPC 2.0 ("result" ou "error").
        """
        req_id = request.get("id")
        method_name = request["method"]
        args, kwargs = protocol.split_params(request.get("params"))

        # 1. Contrôle par table blanche
        self._trace("DISPATCH (table blanche)", req_id, methode=method_name,
                    autorisee=method_name in self.methods)
        if method_name not in self.methods:
            return protocol.make_error(
                req_id, "METHOD_NOT_FOUND",
                f"La méthode '{method_name}' n'est pas autorisée ou n'existe pas.",
                {"available_methods": list(self.methods.keys())})

        func = self.methods[method_name]

        # 2. Vérification des paramètres par rapport à la signature
        problem = self._check_args(func, args, kwargs)
        if problem:
            return protocol.make_error(
                req_id, "INVALID_ARGS", f"Arguments invalides pour '{method_name}' : {problem}",
                {"provided_args": list(kwargs.keys()) if kwargs else len(args)})

        # 3. Exécution protégée
        try:
            t0 = time.perf_counter()
            result = func(*args, **kwargs)
            shown = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
            self._trace("EXECUTE (fonction métier locale)", req_id,
                        appel=f"{getattr(func, '__name__', method_name)}({shown})",
                        resultat=result,
                        duree=f"{(time.perf_counter() - t0) * 1000:.3f} ms")
            return protocol.make_result(req_id, result)
        except Exception as exc:
            return protocol.make_error(req_id, "EXECUTION_ERROR", str(exc),
                                       {"exception_type": type(exc).__name__})

    def stop(self):
        """Arrête le serveur RPC proprement et libère les sockets."""
        self.running = False
        if self._server_socket:
            try:
                # shutdown() réveille le thread bloqué dans accept() (Linux) ;
                # sans cela le port resterait occupé après stop().
                self._server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        with self._clients_lock:
            active = list(self._client_sockets)
            self._client_sockets.clear()
        for sock in active:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=1.0)
