"""
Typage strict (gRPC / Protobuf) vs typage par convention (JSON-RPC, REST).

    python main.py --typing-demo

On envoie à calculate_factorial des paramètres INCORRECTS et on regarde
OÙ l'erreur est détectée et combien d'octets ont traversé le réseau pour rien.
"""

from typing import Any, Dict, List

import grpc
import requests

from cli.ui import explain, section, title
from lab.servers import LabServers
from protos import inventory_pb2
from rpc_core import RPCError
from under_the_hood.tracer import RPCTracer

CASES = [
    ("n = \"abc\" (texte au lieu d'un entier)", {"n": "abc"}),
    ("n = 3.7 (décimal au lieu d'un entier)", {"n": 3.7}),
    ("nombre = 5 (champ inconnu du contrat)", {"nombre": 5}),
]


def _custom(lab, args) -> Dict[str, Any]:
    tracer = RPCTracer()
    client = lab.custom_client(timeout=3, tracer=tracer)
    try:
        res = client.call("calculate_factorial", **args)
        verdict, where = f"accepté → {res}", "—"
    except RPCError as e:
        verdict, where = f"{e.code} ({e.jsonrpc_code}) : {e.message[:70]}", "serveur, après un aller-retour"
    sent = next((int(e["details"]["taille"].split()[0]) + 4 for e in tracer.get_trace()
                 if e["step"].startswith("STUB_MARSHAL")), 0)
    return {"ou": where, "octets": sent, "resultat": verdict}


def _grpc(lab, args) -> Dict[str, Any]:
    try:
        req = inventory_pb2.FactorialRequest(**args)  # construction du message typé
    except (TypeError, ValueError) as e:
        return {"ou": "client, avant tout envoi", "octets": 0, "resultat": f"{type(e).__name__} : {e}"}
    client = lab.grpc_client(timeout=3)
    try:
        res = client.stub.CalculateFactorial(req, timeout=3)
        out = {"ou": "—", "octets": len(req.SerializeToString()) + 5, "resultat": f"accepté → {res.result}"}
    except grpc.RpcError as e:
        out = {"ou": "serveur", "octets": len(req.SerializeToString()) + 5, "resultat": f"{e.code().name} : {e.details()}"}
    client.close()
    return out


def _rest(lab, args) -> Dict[str, Any]:
    body = requests.models.complexjson.dumps(args).encode()
    r = requests.post(f"http://127.0.0.1:{lab.rest_port}/api/factorial", json=args, timeout=3)
    msg = r.json().get("error", r.text) if r.headers.get("Content-Type", "").startswith("application/json") else r.text
    return {"ou": "serveur, après un aller-retour" if not r.ok else "—", "octets": len(body),
            "resultat": f"HTTP {r.status_code} : {str(msg)[:70]}"}


def run_typing_demo() -> Dict[str, Any]:
    title("TYPAGE STRICT — où une erreur de type est-elle détectée ?")
    results: List[Dict[str, Any]] = []
    with LabServers() as lab:
        for label, args in CASES:
            row = {"cas": label, "gRPC": _grpc(lab, args), "Custom RPC": _custom(lab, args), "REST": _rest(lab, args)}
            results.append(row)
            section(label)
            for proto in ("gRPC", "Custom RPC", "REST"):
                r = row[proto]
                print(f"  {proto:<11} détecté : {r['ou']:<31} octets envoyés : {r['octets']:>4}   {r['resultat']}")
    explain("""
gRPC : le message est construit à partir du contrat .proto (champ n : int32). Une valeur
du mauvais type ou un champ inconnu est refusé PAR LE CLIENT, avant tout envoi réseau.
JSON-RPC et REST : JSON n'a pas de schéma imposé ; la requête part, et c'est le serveur
qui découvre l'erreur (n = 3.7 n'est rejeté que parce que le code métier le vérifie).
Octets : message + trame pour gRPC et Custom RPC, corps JSON seul pour REST (sans en-têtes HTTP).""")
    return {"cases": results}
