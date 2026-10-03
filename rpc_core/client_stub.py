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
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional, Dict, Iterator
from . import protocol
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

    def __init__(self, code: str, message: str, data: Optional[Dict[str, Any]] = None,
                 jsonrpc_code: Optional[int] = None):
        self.code = code                      # nom symbolique, ex: "METHOD_NOT_FOUND"
        self.jsonrpc_code = jsonrpc_code      # code numérique JSON-RPC, ex: -32601
        self.message = message
        self.data = data or {}
        super().__init__(f"[{code}] {message}")

    @classmethod
    def from_error(cls, error: Dict[str, Any]) -> "RPCError":
        """Construit l'exception à partir du membre "error" d'une réponse JSON-RPC 2.0."""
        return cls(code=protocol.error_name(error), message=error.get("message", ""),
                   data=error.get("data"), jsonrpc_code=error.get("code"))


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

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        timeout: float = 5.0,
        persistent: bool = False,
        tracer: Optional[Any] = None,
    ):
        """
        Initialise le client RPC.

        Args:
            host: Adresse d'hôte du serveur RPC.
            port: Port d'écoute du serveur RPC.
            timeout: Timeout réseau en secondes pour la connexion et la réponse.
            persistent: Si True, une seule connexion TCP est réutilisée pour tous les
                appels (comme le fait gRPC avec son canal HTTP/2). Si False (défaut),
                chaque appel ouvre puis ferme sa propre connexion TCP : c'est plus
                simple à comprendre mais on paie la poignée de main TCP à chaque appel.
            tracer: RPCTracer optionnel (mode "Sous le capot").
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.persistent = persistent
        self.tracer = tracer
        self.serializer = RPCSerializer()
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None

    def _trace(self, step: str, call_id: Optional[str], **details):
        if self.tracer is not None:
            self.tracer.record_step(step, details, call_id=call_id, side="client")

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
        if self.persistent:
            with self._lock:
                if self._sock is None:
                    self._sock = self.connect()
                try:
                    return self._exchange(self._sock, request_data)
                except Exception:
                    # Connexion dans un état inconnu : on la jette, la prochaine
                    # tentative en rouvrira une neuve.
                    self._close_socket()
                    raise

        sock = self.connect()
        try:
            return self._exchange(sock, request_data)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _exchange(self, sock: socket.socket, request_data: bytes) -> bytes:
        """Un aller-retour requête/réponse sur une socket déjà connectée."""
        try:
            send_message(sock, request_data)
            return receive_message(sock)
        except (socket.timeout, TimeoutError) as err:
            raise TimeoutError(
                f"Timeout ({self.timeout}s) dépassé en attendant la réponse du serveur RPC."
            ) from err
        except ConnectionClosedError as err:
            raise ConnectionError(f"Le serveur RPC a fermé la connexion : {err}") from err
        except TransportError as err:
            raise ConnectionError(f"Erreur de communication réseau : {err}") from err

    @staticmethod
    def _params(args: tuple, kwargs: Dict[str, Any]):
        """JSON-RPC 2.0 : paramètres soit positionnels (tableau), soit nommés (objet), pas les deux."""
        if args and kwargs:
            raise ValueError("JSON-RPC 2.0 : utilisez soit des paramètres positionnels, soit des paramètres nommés.")
        return list(args) if args else dict(kwargs)

    def call(self, method: str, *args, **kwargs) -> Any:
        """
        Exécute un appel distant synchrone (requête JSON-RPC 2.0 avec "id").

            client.call("calculate_factorial", n=5)      # paramètres nommés
            client.call("calculate_factorial", 5)        # paramètres positionnels

        Raises:
            RPCError: si le serveur répond par une erreur JSON-RPC.
            ConnectionError / TimeoutError: si le transport échoue.
        """
        # 1. Stub : construction du message + sérialisation (Marshalling)
        params = self._params(args, kwargs)
        req_bytes = self.serializer.serialize_request(method=method, args=params)
        call_id = None
        if self.tracer is not None:
            call_id = self.serializer.deserialize_request(req_bytes)["id"]
            shown = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
            self._trace("CLIENT_CALL", call_id, code=f"client.{method}({shown})")
            self._trace("STUB_MARSHAL + SERIALIZE (JSON)", call_id, method=method, params=params,
                        payload=req_bytes, taille=f"{len(req_bytes)} octets")
            self._trace("TRANSPORT_SEND (TCP)", call_id, destination=f"{self.host}:{self.port}",
                        trame=f"4 octets d'en-tête (longueur={len(req_bytes)}) + {len(req_bytes)} octets de corps",
                        connexion="persistante" if self.persistent else "nouvelle connexion TCP pour cet appel")

        # 2. Transport réseau (socket TCP)
        resp_bytes = self._send_request(req_bytes)

        # 3. Désérialisation (Unmarshalling)
        response = self.serializer.deserialize_response(resp_bytes)
        self._trace("CLIENT_RECEIVE + UNMARSHAL", call_id, payload=resp_bytes,
                    taille=f"{len(resp_bytes)} octets")

        # 4. Erreur distante -> exception locale
        if "error" in response:
            err = RPCError.from_error(response["error"])
            self._trace("RESULT -> exception levée chez l'appelant", call_id, erreur=err.code)
            raise err

        self._trace("RESULT -> rendu à l'appelant", call_id, resultat=response.get("result"))
        return response.get("result")

    def notify(self, method: str, *args, **kwargs) -> None:
        """
        Notification JSON-RPC 2.0 : requête SANS "id". Le serveur l'exécute mais
        ne répond pas ; l'appelant ne sait donc pas si elle a réussi.
        """
        data = protocol.encode(protocol.make_request(method, self._params(args, kwargs), notification=True))
        if self.persistent:
            with self._lock:
                if self._sock is None:
                    self._sock = self.connect()
                send_message(self._sock, data)
            return
        sock = self.connect()
        try:
            send_message(sock, data)
        finally:
            sock.close()

    def batch(self, calls: list) -> list:
        """
        Lot JSON-RPC 2.0 : plusieurs appels dans UN seul message réseau.

            client.batch([("calculate_factorial", {"n": 5}), ("get_product_details", {"item_id": "PROD-001"})])

        Retourne une liste alignée sur `calls` : le résultat, ou une RPCError (non levée).
        """
        requests = [protocol.make_request(m, p if p is not None else {}) for m, p in calls]
        resp_bytes = self._send_request(protocol.encode(requests))
        responses = protocol.decode(resp_bytes)
        if isinstance(responses, dict):  # le serveur a rejeté le lot entier
            protocol.validate_response(responses)
            raise RPCError.from_error(responses["error"])
        by_id = {}
        for r in responses:
            protocol.validate_response(r)
            by_id[r["id"]] = r
        out = []
        for req in requests:
            r = by_id.get(req["id"])
            if r is None:
                out.append(RPCError("INTERNAL_ERROR", "Aucune réponse reçue pour cette requête."))
            elif "error" in r:
                out.append(RPCError.from_error(r["error"]))
            else:
                out.append(r["result"])
        return out

    def stream(self, method: str, **kwargs) -> Iterator[Any]:
        """
        Appel en STREAMING : retourne un itérateur qui produit les éléments au fur
        et à mesure de leur arrivée (une notification "rpc.stream.item" par élément).

            for event in client.stream("stream_analytics", metric_name="cpu_usage", num_events=5):
                print(event)   # affiché dès réception, sans attendre la fin du flux

        Le flux utilise sa propre connexion TCP, fermée à la fin (ou si l'appelant
        arrête d'itérer avant la fin : le serveur s'en aperçoit et s'arrête).
        Le timeout s'applique à l'attente de CHAQUE trame.
        """
        request = protocol.make_request(protocol.STREAM_METHOD, {"method": method, "params": dict(kwargs)})
        req_bytes = protocol.encode(request)
        call_id = None
        if self.tracer is not None:
            call_id = request["id"]
            self._trace("CLIENT_CALL (flux)", call_id, code=f"client.stream({method!r}, {kwargs})")
            self._trace("STUB_MARSHAL + SERIALIZE (JSON)", call_id, payload=req_bytes,
                        taille=f"{len(req_bytes)} octets")
        return self._stream_frames(req_bytes, call_id, request["id"])

    def _stream_frames(self, req_bytes: bytes, call_id: Optional[str], req_id: str) -> Iterator[Any]:
        sock = self.connect()
        try:
            try:
                send_message(sock, req_bytes)
            except TransportError as err:
                raise ConnectionError(f"Erreur de communication réseau : {err}") from err
            while True:
                try:
                    frame_bytes = receive_message(sock)
                except (socket.timeout, TimeoutError) as err:
                    raise TimeoutError(
                        f"Timeout ({self.timeout}s) dépassé en attendant la trame suivante du flux."
                    ) from err
                except ConnectionClosedError as err:
                    raise ConnectionError(f"Flux interrompu : le serveur a fermé la connexion ({err}).") from err
                except TransportError as err:
                    raise ConnectionError(f"Erreur de communication réseau : {err}") from err
                frame = protocol.decode(frame_bytes)
                # Notification "rpc.stream.item" : un élément du flux
                if isinstance(frame, dict) and frame.get("method") == protocol.STREAM_ITEM_METHOD:
                    p = frame.get("params") or {}
                    self._trace(f"STREAM_RECEIVE trame n°{p.get('seq')}", call_id,
                                taille=f"{len(frame_bytes)} octets")
                    yield p.get("item")
                    continue
                # Sinon : LA réponse finale à la requête rpc.stream
                protocol.validate_response(frame)
                if "error" in frame:
                    err = RPCError.from_error(frame["error"])
                    self._trace("STREAM_ERROR", call_id, erreur=err.code)
                    raise err
                self._trace("STREAM_END reçu", call_id, nombre=(frame.get("result") or {}).get("count"))
                return
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def call_async(self, method: str, *args, **kwargs) -> Future:
        """
        Appel asynchrone : retourne immédiatement un `Future`.

        L'appelant peut continuer à travailler puis récupérer le résultat avec
        `future.result()` (qui relance l'éventuelle exception distante).
        """
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="rpc-async")
        return self._executor.submit(self.call, method, *args, **kwargs)

    def __getattr__(self, name: str):
        """
        Permet l'invocation dynamique transparente :
        client.calculate_factorial(n=5) équivaut à client.call("calculate_factorial", n=5)
        """
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' n'a pas d'attribut '{name}'")

        def dynamic_stub(*args, **kwargs):
            return self.call(name, *args, **kwargs)

        return dynamic_stub

    def _close_socket(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def close(self):
        """Ferme la connexion persistante éventuelle et le pool asynchrone."""
        with self._lock:
            self._close_socket()
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
