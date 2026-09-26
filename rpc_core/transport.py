"""
Transport Layer pour Custom RPC

Fournit l'envoi et la réception fiables de messages sur socket TCP avec framing par préfixe de longueur.

Protocole de framing:
┌───────────────────────┬───────────────────────────────────────────┐
│ Longueur (4 octets,   │ Corps du message JSON (N octets)          │
│ big-endian uint32)    │                                           │
└───────────────────────┴───────────────────────────────────────────┘
"""

import socket
import struct
from typing import Optional


class TransportError(Exception):
    """Exception levée en cas de défaillance réseau ou de protocole de transport."""
    pass


class ConnectionClosedError(TransportError):
    """Exception levée lorsque la connexion est fermée par le pair distant."""
    pass


def send_message(sock: socket.socket, data: bytes):
    """
    Envoie un message complet préfixé par sa longueur sur une socket TCP.

    Args:
        sock: Socket connectée.
        data: Données brutes à transmettre.

    Raises:
        TransportError: En cas d'erreur de transmission socket.
    """
    try:
        length = len(data)
        header = struct.pack(">I", length)
        sock.sendall(header + data)
    except (socket.error, OSError) as err:
        raise TransportError(f"Échec de transmission socket : {err}") from err


def receive_message(sock: socket.socket) -> bytes:
    """
    Lit un message complet préfixé par sa longueur depuis une socket TCP.

    Args:
        sock: Socket connectée.

    Returns:
        bytes: Données du message reçu.

    Raises:
        ConnectionClosedError: Si le socket est fermé avant d'avoir reçu le message.
        TransportError: En cas d'erreur de lecture réseau.
    """
    # 1. Lecture de l'en-tête de 4 octets
    header_data = _recv_all(sock, 4)
    if not header_data:
        raise ConnectionClosedError("Connexion fermée par le pair distant (en-tête vide).")

    if len(header_data) < 4:
        raise TransportError(f"En-tête incomplet reçu ({len(header_data)}/4 octets).")

    (message_length,) = struct.unpack(">I", header_data)

    # 2. Lecture du corps du message
    body = _recv_all(sock, message_length)
    if len(body) < message_length:
        raise ConnectionClosedError(
            f"Connexion fermée prématurément ({len(body)}/{message_length} octets reçus)."
        )

    return body


def _recv_all(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Lit exactement num_bytes depuis la socket en boucle jusqu'à complétion ou EOF.
    """
    buffer = bytearray()
    while len(buffer) < num_bytes:
        try:
            chunk = sock.recv(min(num_bytes - len(buffer), 4096))
        except (socket.timeout, TimeoutError):
            raise TimeoutError("Timeout dépassé lors de la lecture sur la socket TCP.")
        except (socket.error, OSError) as err:
            raise TransportError(f"Erreur lors de la lecture socket : {err}") from err

        if not chunk:
            break
        buffer.extend(chunk)
    return bytes(buffer)
