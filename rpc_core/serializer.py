"""
RPC Serializer

Ce module gère la sérialisation/désérialisation des messages RPC Custom en JSON UTF-8.

Format de message:
- Requête: {"id": str, "method": str, "args": dict, "metadata": dict}
- Réponse: {"id": str, "result": any, "error": dict|None, "metadata": dict}
- Erreur:  {"code": str, "message": str, "data": dict}
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class RPCSerializer:
    """
    Sérialiseur/Désérialiseur pour les messages RPC Custom.

    Responsabilités:
    - Encoder une requête RPC en JSON bytes UTF-8
    - Décoder une requête RPC depuis JSON bytes UTF-8
    - Encoder une réponse RPC en JSON bytes UTF-8
    - Décoder une réponse RPC depuis JSON bytes UTF-8
    - Validation rigoureuse des schémas de message
    """

    @staticmethod
    def serialize_request(method: str, args: Dict[str, Any],
                          request_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Sérialise une requête RPC en JSON bytes.

        Args:
            method: Nom de la méthode à appeler.
            args: Dictionnaire d'arguments.
            request_id: ID unique de la requête (auto-généré si None).
            metadata: Métadonnées additionnelles.

        Returns:
            bytes: Message JSON encodé en UTF-8.
        """
        if not method or not isinstance(method, str):
            raise ValueError("Le paramètre 'method' doit être une chaîne non vide.")
        if not isinstance(args, dict):
            raise ValueError("Le paramètre 'args' doit être un dictionnaire.")

        req_id = request_id or str(uuid.uuid4())
        meta = metadata.copy() if metadata else {}
        if "timestamp" not in meta:
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()

        payload = {
            "id": req_id,
            "method": method,
            "args": args,
            "metadata": meta
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @classmethod
    def deserialize_request(cls, data: bytes) -> Dict[str, Any]:
        """
        Désérialise une requête RPC depuis JSON bytes.

        Args:
            data: Message JSON en bytes.

        Returns:
            dict: Requête validée avec clés: id, method, args, metadata.

        Raises:
            ValueError: Si le format ou le schéma JSON est invalide.
        """
        if not data:
            raise ValueError("Données reçues vides.")

        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise ValueError(f"Erreur de décodage JSON : {err}") from err

        if not cls.validate_request(decoded):
            raise ValueError(f"Structure de requête RPC invalide : {decoded}")

        return decoded

    @staticmethod
    def serialize_response(request_id: str, result: Any = None,
                           error: Optional[Dict[str, Any]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Sérialise une réponse RPC en JSON bytes.

        Args:
            request_id: ID de la requête correspondante.
            result: Résultat de l'exécution (si succès).
            error: Dictionnaire d'erreur structuré (si échec).
            metadata: Métadonnées additionnelles.

        Returns:
            bytes: Message JSON encodé en UTF-8.
        """
        if not request_id or not isinstance(request_id, str):
            raise ValueError("Le paramètre 'request_id' doit être une chaîne non vide.")

        meta = metadata.copy() if metadata else {}
        if "timestamp" not in meta:
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()

        payload = {
            "id": request_id,
            "result": result,
            "error": error,
            "metadata": meta
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @classmethod
    def deserialize_response(cls, data: bytes) -> Dict[str, Any]:
        """
        Désérialise une réponse RPC depuis JSON bytes.

        Args:
            data: Message JSON en bytes.

        Returns:
            dict: Réponse validée avec clés: id, result, error, metadata.

        Raises:
            ValueError: Si le format ou le schéma JSON est invalide.
        """
        if not data:
            raise ValueError("Données reçues vides.")

        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise ValueError(f"Erreur de décodage JSON : {err}") from err

        if not cls.validate_response(decoded):
            raise ValueError(f"Structure de réponse RPC invalide : {decoded}")

        return decoded

    @staticmethod
    def validate_request(request: Dict[str, Any]) -> bool:
        """
        Valide la structure d'une requête RPC.

        Critères:
        - Doit être un dictionnaire
        - Clés requises: id (str), method (str non vide), args (dict)
        """
        if not isinstance(request, dict):
            return False
        if not isinstance(request.get("id"), str) or not request["id"]:
            return False
        if not isinstance(request.get("method"), str) or not request["method"]:
            return False
        if not isinstance(request.get("args"), dict):
            return False
        return True

    @staticmethod
    def validate_response(response: Dict[str, Any]) -> bool:
        """
        Valide la structure d'une réponse RPC.

        Critères:
        - Doit être un dictionnaire
        - Clés requises: id (str non vide), result, error
        - error doit être None ou un dictionnaire contenant au minimum code et message
        """
        if not isinstance(response, dict):
            return False
        if not isinstance(response.get("id"), str) or not response["id"]:
            return False
        if "result" not in response or "error" not in response:
            return False
        error = response.get("error")
        if error is not None:
            if not isinstance(error, dict):
                return False
            if "code" not in error or "message" not in error:
                return False
        return True
