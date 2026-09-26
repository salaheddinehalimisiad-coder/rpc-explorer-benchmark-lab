"""
RPC Core Package

Implémentation complète du mini-framework RPC Custom (from scratch) pour les besoins pédagogiques :
- serializer.py : Sérialisation et validation JSON UTF-8
- transport.py : Transmission réseau TCP avec cadrage de trame par préfixe de longueur (4 octets)
- client_stub.py : Client RPC avec transparence d'appel (méthode call et invocation dynamique)
- server_skeleton.py : Squelette serveur TCP multi-threadé avec dispatcher sécurisé par table blanche
"""

from .serializer import RPCSerializer
from .transport import send_message, receive_message, TransportError, ConnectionClosedError
from .client_stub import RPCClient, RPCError
from .server_skeleton import (
    RPCServer,
    RPCMethodNotFoundError,
    RPCInvalidArgsError,
    RPCServerError
)

__version__ = "1.0.0"
__all__ = [
    "RPCSerializer",
    "send_message",
    "receive_message",
    "TransportError",
    "ConnectionClosedError",
    "RPCClient",
    "RPCError",
    "RPCServer",
    "RPCMethodNotFoundError",
    "RPCInvalidArgsError",
    "RPCServerError",
]
