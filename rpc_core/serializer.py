"""
RPC Serializer (marshalling / unmarshalling) du Custom RPC.

Transforme les appels et les résultats Python en octets JSON au format
JSON-RPC 2.0, et inversement. Le format lui-même est défini dans protocol.py ;
cette classe en est la façade utilisée par le stub client et le skeleton serveur.

    RPCSerializer.serialize_request("calculate_factorial", {"n": 5})
    -> b'{"jsonrpc":"2.0","method":"calculate_factorial","params":{"n":5},"id":"9f1c..."}'
"""

from typing import Any, Dict, Optional, Union

from . import protocol


class RPCSerializer:
    """Encodage / décodage des messages JSON-RPC 2.0 (UTF-8)."""

    @staticmethod
    def serialize_request(method: str, args: Union[Dict[str, Any], list, None],
                          request_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Sérialise une requête JSON-RPC 2.0.

        Args:
            method: nom de la méthode distante.
            args: paramètres nommés (dict) ou positionnels (list).
            request_id: identifiant de corrélation (UUID généré si absent).
            metadata: conservé pour compatibilité ; JSON-RPC 2.0 ne prévoit pas
                de métadonnées, elles ne sont donc pas transmises.
        """
        if not method or not isinstance(method, str):
            raise ValueError("Le paramètre 'method' doit être une chaîne non vide.")
        if not isinstance(args, (dict, list)):
            raise ValueError("Le paramètre 'args' doit être un dictionnaire (ou une liste).")
        return protocol.encode(protocol.make_request(method, args, id=request_id))

    @classmethod
    def deserialize_request(cls, data: bytes) -> Dict[str, Any]:
        """Octets -> requête JSON-RPC 2.0 validée. Lève ValueError si invalide."""
        msg = protocol.decode(data)
        protocol.validate_request(msg)
        return msg

    @staticmethod
    def serialize_response(request_id: Optional[Union[str, int]], result: Any = None,
                           error: Optional[Dict[str, Any]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Sérialise une réponse JSON-RPC 2.0.

        `error` peut porter un code numérique JSON-RPC ou un nom symbolique
        ("METHOD_NOT_FOUND", "INVALID_ARGS"…), converti en code numérique.
        """
        if error is not None:
            msg = protocol.make_error(request_id, error.get("code", "INTERNAL_ERROR"),
                                      error.get("message", ""), error.get("data"))
        else:
            msg = protocol.make_result(request_id, result)
        return protocol.encode(msg)

    @classmethod
    def deserialize_response(cls, data: bytes) -> Dict[str, Any]:
        """Octets -> réponse JSON-RPC 2.0 validée. Lève ValueError si invalide."""
        msg = protocol.decode(data)
        protocol.validate_response(msg)
        return msg

    @staticmethod
    def validate_request(request: Any) -> bool:
        try:
            protocol.validate_request(request)
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_response(response: Any) -> bool:
        try:
            protocol.validate_response(response)
            return True
        except ValueError:
            return False
