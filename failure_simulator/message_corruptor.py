"""
Module de corruption de messages et requetes (Phase 07).

Fournit des utilitaires pour fabriquer des requetes ou charges utiles malformees
afin d'observer le comportement des validateurs, deserialiseurs et dispatchers
sur chaque protocole :
- Custom RPC : JSON malforme ou payload tronque (JSONDecodeError, RPCProtocolError)
- gRPC / Protobuf : Octets incompatibles avec le contrat IDL (DecodeError / RpcError)
- REST : Corps HTTP invalide ou methode inconnue (400 Bad Request, 404 Not Found)
"""

from typing import Any, Dict


class MessageCorruptor:
    """
    Generateur de messages et donnees corrompues pour les tests de robustesse.
    """

    @staticmethod
    def create_invalid_json() -> bytes:
        """Genere des octets JSON syntaxiquement invalides."""
        return b"{invalid json syntax: [unclosed"

    @staticmethod
    def create_truncated_json() -> bytes:
        """Genere un JSON tronque simulant une rupture de flux TCP."""
        return b'{"id": "req-123", "method": "calculate_factorial", "args":'

    @staticmethod
    def create_invalid_protobuf() -> bytes:
        """
        Genere des octets aleatoires ou non conformes a un message Protobuf valide.
        Provoque une erreur de decodage (google.protobuf.message.DecodeError).
        """
        return b"\xff\xfe\xfd\xfc\xfb\x80\x90\xa0\xb0\xc0"

    @staticmethod
    def create_unknown_method_request(
        req_id: str = "req_corrupt_01",
        method_name: str = "__non_existent_method__"
    ) -> Dict[str, Any]:
        """Genere un dictionnaire de requete avec une methode non declaree."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method_name,
            "params": {},
        }

    @staticmethod
    def create_invalid_schema_request() -> Dict[str, Any]:
        """Genere un dictionnaire ne respectant pas le schema de requete Custom RPC."""
        return {
            "bad_key": "bad_value",
            "not_an_id": 99999
        }

    @staticmethod
    def corrupt_bytes(data: bytes, offset: int = 0) -> bytes:
        """
        Altere un octet dans une charge utile binaire.

        Args:
            data: Octets d'origine.
            offset: Index de l'octet a corrompre.

        Returns:
            Nouvelle sequence d'octets avec l'octet modifie.
        """
        if not data:
            return b"\xff"
        idx = max(0, min(offset, len(data) - 1))
        mutated = bytearray(data)
        mutated[idx] ^= 0xFF  # Inversion de tous les bits
        return bytes(mutated)
