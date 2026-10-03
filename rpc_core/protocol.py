"""
Format des messages du Custom RPC : spécification JSON-RPC 2.0.

Référence : https://www.jsonrpc.org/specification

Requête            {"jsonrpc": "2.0", "method": "update_stock", "params": {...} | [...], "id": "a1b2"}
Notification       {"jsonrpc": "2.0", "method": "log", "params": {...}}        (pas d'"id" : pas de réponse)
Réponse (succès)   {"jsonrpc": "2.0", "result": ..., "id": "a1b2"}
Réponse (erreur)   {"jsonrpc": "2.0", "error": {"code": -32601, "message": "...", "data": {...}}, "id": "a1b2"}
Lot (batch)        [requête, requête, notification, ...]  ->  [réponse, réponse, ...]

Codes d'erreur : ceux de la spécification (-32700 à -32603) ; la plage -32000 à -32099
est réservée aux erreurs définies par l'implémentation (voir ERROR_CODES).
Chaque erreur porte aussi son nom symbolique dans error.data.name (ex: "METHOD_NOT_FOUND"),
plus lisible pour l'appelant et pour la démonstration.

Extension de streaming (le streaming n'existe pas dans JSON-RPC 2.0) :
  - le client appelle la méthode réservée "rpc.stream" avec params = {"method": ..., "params": ...}
    (le préfixe "rpc." est réservé par la spécification aux extensions du système) ;
  - le serveur envoie une NOTIFICATION "rpc.stream.item" par élément :
        {"jsonrpc": "2.0", "method": "rpc.stream.item", "params": {"id": <id de la requête>, "seq": n, "item": ...}}
  - puis UNE réponse normale à la requête : {"jsonrpc": "2.0", "result": {"count": N}, "id": ...}
    (ou une réponse d'erreur si le flux échoue).
  Chaque message reste donc un objet JSON-RPC 2.0 valide, et la requête reçoit exactement une réponse.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

JSONRPC_VERSION = "2.0"
STREAM_METHOD = "rpc.stream"
STREAM_ITEM_METHOD = "rpc.stream.item"

# nom symbolique -> code numérique JSON-RPC
ERROR_CODES: Dict[str, int] = {
    "PARSE_ERROR": -32700,        # JSON illisible
    "INVALID_REQUEST": -32600,    # JSON valide mais pas une requête JSON-RPC
    "METHOD_NOT_FOUND": -32601,   # méthode absente de la table blanche
    "INVALID_ARGS": -32602,       # « Invalid params » dans la spécification
    "INTERNAL_ERROR": -32603,     # erreur interne du serveur RPC
    "EXECUTION_ERROR": -32000,    # la fonction métier a levé une exception
    "STREAM_NOT_SUPPORTED": -32001,
}
ERROR_NAMES: Dict[int, str] = {v: k for k, v in ERROR_CODES.items()}

Id = Union[str, int, None]
Params = Union[Dict[str, Any], List[Any]]


class ProtocolError(ValueError):
    """Message qui ne respecte pas JSON-RPC 2.0. `name` est le nom symbolique de l'erreur."""

    def __init__(self, name: str, message: str):
        super().__init__(message)
        self.name = name


def new_id() -> str:
    return str(uuid.uuid4())


# ── Construction ──────────────────────────────────────────────────────────
def make_request(method: str, params: Optional[Params] = None, id: Id = None,
                 notification: bool = False) -> Dict[str, Any]:
    if not isinstance(method, str) or not method:
        raise ValueError("Le paramètre 'method' doit être une chaîne non vide.")
    if params is not None and not isinstance(params, (dict, list)):
        raise ValueError("Le paramètre 'params' doit être un objet (dict) ou un tableau (list).")
    msg: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        msg["params"] = params
    if not notification:
        msg["id"] = id if id is not None else new_id()
    return msg


def make_result(id: Id, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "result": result, "id": id}


def make_error(id: Id, name_or_code: Union[str, int], message: str,
               data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Réponse d'erreur. Accepte un nom symbolique ("METHOD_NOT_FOUND") ou un code numérique."""
    if isinstance(name_or_code, int):
        code, name = name_or_code, ERROR_NAMES.get(name_or_code, "SERVER_ERROR")
    else:
        name = name_or_code
        code = ERROR_CODES.get(name, ERROR_CODES["INTERNAL_ERROR"])
    payload = dict(data or {})
    payload.setdefault("name", name)
    return {"jsonrpc": JSONRPC_VERSION, "error": {"code": code, "message": str(message), "data": payload}, "id": id}


def make_stream_item(request_id: Id, seq: int, item: Any) -> Dict[str, Any]:
    return make_request(STREAM_ITEM_METHOD, {"id": request_id, "seq": seq, "item": item}, notification=True)


# ── Validation ────────────────────────────────────────────────────────────
def is_request(msg: Any) -> bool:
    return isinstance(msg, dict) and "method" in msg


def is_notification(msg: Dict[str, Any]) -> bool:
    return is_request(msg) and "id" not in msg


def validate_request(msg: Any) -> None:
    """Lève ProtocolError("INVALID_REQUEST") si `msg` n'est pas une requête JSON-RPC 2.0."""
    if not isinstance(msg, dict):
        raise ProtocolError("INVALID_REQUEST", "Une requête doit être un objet JSON.")
    if msg.get("jsonrpc") != JSONRPC_VERSION:
        raise ProtocolError("INVALID_REQUEST", 'Le membre "jsonrpc" doit valoir exactement "2.0".')
    if not isinstance(msg.get("method"), str) or not msg["method"]:
        raise ProtocolError("INVALID_REQUEST", 'Le membre "method" doit être une chaîne non vide.')
    if "params" in msg and not isinstance(msg["params"], (dict, list)):
        raise ProtocolError("INVALID_REQUEST", 'Le membre "params" doit être un objet ou un tableau.')
    if "id" in msg and not (msg["id"] is None or isinstance(msg["id"], (str, int)) and not isinstance(msg["id"], bool)):
        raise ProtocolError("INVALID_REQUEST", 'Le membre "id" doit être une chaîne, un entier ou null.')


def validate_response(msg: Any) -> None:
    """Lève ValueError si `msg` n'est pas une réponse JSON-RPC 2.0."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != JSONRPC_VERSION:
        raise ValueError(f"Réponse JSON-RPC 2.0 invalide : {msg!r}")
    if "id" not in msg:
        raise ValueError('Une réponse doit contenir le membre "id".')
    if ("result" in msg) == ("error" in msg):
        raise ValueError('Une réponse contient soit "result", soit "error", jamais les deux ni aucun.')
    if "error" in msg:
        err = msg["error"]
        if not isinstance(err, dict) or not isinstance(err.get("code"), int) or "message" not in err:
            raise ValueError('Le membre "error" doit contenir "code" (entier) et "message".')


# ── Encodage / décodage ───────────────────────────────────────────────────
def encode(msg: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bytes:
    return json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decode(data: bytes) -> Any:
    """Octets -> objet Python. Lève ProtocolError("PARSE_ERROR") si ce n'est pas du JSON."""
    if not data:
        raise ProtocolError("PARSE_ERROR", "Message vide.")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ProtocolError("PARSE_ERROR", f"Erreur de décodage JSON : {err}") from err


def error_name(error: Dict[str, Any]) -> str:
    """Nom symbolique d'une erreur JSON-RPC (data.name, sinon d'après le code)."""
    data = error.get("data") or {}
    return data.get("name") or ERROR_NAMES.get(error.get("code"), f"JSONRPC_{error.get('code')}")


def split_params(params: Optional[Params]) -> Tuple[List[Any], Dict[str, Any]]:
    """params JSON-RPC -> (args positionnels, kwargs) pour l'appel Python."""
    if params is None:
        return [], {}
    if isinstance(params, list):
        return list(params), {}
    return [], dict(params)
