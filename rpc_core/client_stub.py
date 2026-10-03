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
        # 1. Stub : construction du message + sérialisation (Marshaling)
        req_bytes = self.serializer.serialize_request(method=method, args=kwargs)
        call_id = None
        if self.tracer is not None:
            call_id = self.serializer.deserialize_request(req_bytes)["id"]
            self._trace("CLIENT_CALL", call_id, code=f"client.{method}({', '.join(f'{k}={v!r}' for k, v in kwargs.items())})")
            self._trace("STUB_MARSHAL + SERIALIZE (JSON)", call_id, method=method, args=kwargs,
                        payload=req_bytes, taille=f"{len(req_bytes)} octets")
            self._trace("TRANSPORT_SEND (TCP)", call_id, destination=f"{self.host}:{self.port}",
                        trame=f"4 octets d'en-tête (longueur={len(req_bytes)}) + {len(req_bytes)} octets de corps",
                        connexion="persistante" if self.persistent else "nouvelle connexion TCP pour cet appel")

        # 2. Transport réseau (Socket TCP)
        resp_bytes = self._send_request(req_bytes)

        # 3. Désérialisation (Unmarshaling)
        response = self.serializer.deserialize_response(resp_bytes)
        self._trace("CLIENT_RECEIVE + UNMARSHAL", call_id, payload=resp_bytes,
                    taille=f"{len(resp_bytes)} octets")

        # 4. Vérification d'erreur applicative
        if response.get("error") is not None:
            err = response["error"]
            self._trace("RESULT -> exception levée chez l'appelant", call_id, erreur=err.get("code"))
            raise RPCError(
                code=err.get("code", "RPC_GENERIC_ERROR"),
                message=err.get("message", "Une erreur distante s'est produite"),
                data=err.get("data")
            )

        self._trace("RESULT -> rendu à l'appelant", call_id, resultat=response.get("result"))
        return response.get("result")

    def stream(self, method: str, **kwargs) -> Iterator[Any]:
        """
        Appel en STREAMING : retourne un itérateur qui produit les éléments au fur
        et à mesure de leur arrivée (une trame réseau par élément).

            for event in client.stream("stream_analytics", metric_name="cpu_usage", num_events=5):
                print(event)   # affiché dès réception, sans attendre la fin du flux

        Le flux utilise sa propre connexion TCP, fermée à la fin (ou si l'appelant
        arrête d'itérer avant la fin : le serveur s'en aperçoit et s'arrête).
        Le timeout s'applique à l'attente de CHAQUE trame.
        """
        req_bytes = self.serializer.serialize_request(method=method, args=kwargs,
                                                      metadata={"stream": True})
        call_id = None
        if self.tracer is not None:
            call_id = self.serializer.deserialize_request(req_bytes)["id"]
            self._trace("CLIENT_CALL (flux)", call_id, code=f"client.stream({method!r}, {kwargs})")
            self._trace("STUB_MARSHAL + SERIALIZE (JSON)", call_id, payload=req_bytes,
                        taille=f"{len(req_bytes)} octets")
        return self._stream_frames(req_bytes, call_id)

    def _stream_frames(self, req_bytes: bytes, call_id: Optional[str]) -> Iterator[Any]:
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
                frame = self.serializer.deserialize_response(frame_bytes)
                kind = (frame.get("metadata") or {}).get("stream")
                if frame.get("error") is not None:
                    err = frame["error"]
                    self._trace("STREAM_ERROR", call_id, erreur=err.get("code"))
                    raise RPCError(code=err.get("code", "RPC_GENERIC_ERROR"),
                                   message=err.get("message", "Erreur distante pendant le flux"),
                                   data=err.get("data"))
                if kind == "end":
                    self._trace("STREAM_END reçu", call_id, nombre=frame["metadata"].get("count"))
                    return
                self._trace(f"STREAM_RECEIVE trame n°{frame['metadata'].get('seq')}", call_id,
                            taille=f"{len(frame_bytes)} octets")
                yield frame.get("result")
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def call_async(self, method: str, **kwargs) -> Future:
        """
        Appel asynchrone : retourne immédiatement un `Future`.

        L'appelant peut continuer à travailler puis récupérer le résultat avec
        `future.result()` (qui relance l'éventuelle exception distante).
        """
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="rpc-async")
        return self._executor.submit(self.call, method, **kwargs)

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
