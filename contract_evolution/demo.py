"""
Démonstration de l'ÉVOLUTION DE CONTRAT (Phase 10).

Question posée : « Que se passe-t-il quand le serveur passe en version N+1
alors que des clients en version N tournent encore ? »

Deux mondes très différents :

* Custom RPC (JSON) — les arguments voyagent PAR NOM ({"quantity_delta": -3}).
  Renommer un paramètre casse l'appel, mais l'erreur est explicite.
  Il n'y a AUCUN contrat écrit : on ne découvre le problème qu'à l'exécution.

* gRPC (Protobuf) — les champs voyagent PAR NUMÉRO (champ n°2 = -3).
  Renommer un champ est sans danger, mais renuméroter ou changer le type
  d'un champ produit des BUGS SILENCIEUX : pas d'erreur, mauvaises données.

    python main.py --contract-demo
"""

import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import grpc

from business.inventory_service import InventoryService
from cli.ui import explain, green, red, section, table, title, yellow
from protos import inventory_pb2 as v1
from protos import inventory_pb2_grpc as v1_grpc
from rpc_core import RPCClient, RPCError, RPCServer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMPATIBLE = "COMPATIBLE"
BREAKING_LOUD = "BREAKING (erreur visible)"
BREAKING_SILENT = "BREAKING (bug SILENCIEUX)"


def _row(scenario: str, change: str, observed: str, verdict: str) -> Dict[str, str]:
    return {"scenario": scenario, "change": change, "observed": observed, "verdict": verdict}


# ═════════════════════════════════════════════════════════════════════════
# 1. CUSTOM RPC
# ═════════════════════════════════════════════════════════════════════════
class InventoryServiceV2Custom:
    """Version 2 du service exposé en Custom RPC (signatures modifiées)."""

    def __init__(self):
        self._svc = InventoryService()

    # [COMPATIBLE] nouveau paramètre OPTIONNEL + nouvelles clés dans la réponse
    def get_product_details(self, item_id: str, include_supplier: bool = False) -> Dict[str, Any]:
        p = dict(self._svc.get_product_details(item_id))
        p["currency"] = "EUR"
        if include_supplier:
            p["supplier"] = "ACME"
        return p

    # [BREAKING] paramètre renommé : quantity_delta -> delta
    def update_stock(self, item_id: str, delta: int) -> Dict[str, Any]:
        return self._svc.update_stock(item_id, delta)

    # [BREAKING] méthode renommée : calculate_factorial -> compute_factorial
    def compute_factorial(self, n: int) -> int:
        return self._svc.calculate_factorial(n)


def run_custom_rpc_scenarios() -> List[Dict[str, str]]:
    rows = []
    # Baseline : client v1 -> serveur v1
    s1 = RPCServer(port=0)
    s1.register_service(InventoryService(), ["calculate_factorial", "update_stock", "get_product_details"])
    s1.start()
    try:
        c = RPCClient(port=s1.port, timeout=2)
        r = c.update_stock(item_id="PROD-001", quantity_delta=-3)
        rows.append(_row("Client v1 → Serveur v1", "aucun (référence)",
                         f"OK, stock {r['previous_stock']} -> {r['new_stock']}", COMPATIBLE))
    finally:
        s1.stop()

    # Client v1 -> serveur v2
    svc2 = InventoryServiceV2Custom()
    s2 = RPCServer(port=0)
    s2.register_service(svc2, ["get_product_details", "update_stock", "compute_factorial"])
    s2.start()
    try:
        c = RPCClient(port=s2.port, timeout=2)
        p = c.get_product_details(item_id="PROD-001")
        rows.append(_row("get_product_details", "v2 ajoute un paramètre optionnel + un champ 'currency'",
                         f"OK (le client v1 reçoit une clé en plus : currency={p.get('currency')})", COMPATIBLE))
        try:
            c.update_stock(item_id="PROD-001", quantity_delta=-3)
            rows.append(_row("update_stock", "paramètre renommé quantity_delta -> delta", "succès inattendu", "?"))
        except RPCError as e:
            rows.append(_row("update_stock", "paramètre renommé quantity_delta -> delta",
                             f"RPCError {e.code}", BREAKING_LOUD))
        try:
            c.calculate_factorial(n=5)
            rows.append(_row("calculate_factorial", "méthode renommée -> compute_factorial", "succès inattendu", "?"))
        except RPCError as e:
            rows.append(_row("calculate_factorial", "méthode renommée -> compute_factorial",
                             f"RPCError {e.code}", BREAKING_LOUD))
    finally:
        s2.stop()
    return rows


# ═════════════════════════════════════════════════════════════════════════
# 2. gRPC / PROTOBUF
# ═════════════════════════════════════════════════════════════════════════
class ServerV2Process:
    """Lance contract_evolution.server_v2 dans un processus séparé."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.proc: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None

    def __enter__(self):
        env = dict(os.environ, PYTHONPATH=PROJECT_ROOT + os.pathsep + os.environ.get("PYTHONPATH", ""))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "contract_evolution.server_v2", "--port", "0"],
            cwd=PROJECT_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if line.startswith("READY"):
                self.port = int(line.split()[1])
                return self
            if self.proc.poll() is not None:
                break
        err = self.proc.stderr.read() if self.proc.poll() is not None else ""
        self.__exit__(None, None, None)
        raise RuntimeError(f"Le serveur v2 n'a pas démarré : {err}")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.proc:
            for stream in (self.proc.stdout, self.proc.stderr):
                if stream:
                    stream.close()


def _unknown_fields_count(msg) -> int:
    try:
        from google.protobuf.unknown_fields import UnknownFieldSet
        return len(UnknownFieldSet(msg))
    except Exception:  # API absente sur de vieilles versions de protobuf
        return -1


def run_grpc_scenarios(port_v1: Optional[int] = None) -> List[Dict[str, str]]:
    rows = []
    # Baseline v1 -> v1
    from grpc_impl.grpc_server import InventoryGRPCServer
    srv1 = InventoryGRPCServer(port=0)
    p1 = srv1.start()
    try:
        with grpc.insecure_channel(f"127.0.0.1:{p1}") as ch:
            stub = v1_grpc.InventoryRPCServiceStub(ch)
            r = stub.UpdateStock(v1.UpdateStockRequest(item_id="PROD-001", quantity_delta=-3), timeout=3)
            rows.append(_row("Client v1 → Serveur v1", "aucun (référence)",
                             f"OK, nouveau stock = {r.quantity} (42 - 3)", COMPATIBLE))
    finally:
        srv1.stop(grace=0.1)

    with ServerV2Process() as v2, grpc.insecure_channel(f"127.0.0.1:{v2.port}") as ch:
        stub = v1_grpc.InventoryRPCServiceStub(ch)  # <- stub GÉNÉRÉ depuis le contrat v1

        # a) champ renommé (même numéro) + nouveaux champs
        r = stub.GetProductDetails(v1.ProductRequest(item_id="PROD-001"), timeout=3)
        n_unknown = _unknown_fields_count(r)
        extra = f", {n_unknown} champ(s) inconnu(s) ignoré(s)" if n_unknown >= 0 else ""
        rows.append(_row("GetProductDetails",
                         "item_id renommé product_id (même n°1) + champs n°8,9 ajoutés",
                         f"OK : '{r.name}'{extra}", COMPATIBLE))

        # b) renumérotation
        r = stub.UpdateStock(v1.UpdateStockRequest(item_id="PROD-001", quantity_delta=-3), timeout=3)
        rows.append(_row("UpdateStock",
                         "quantity_delta déplacé du n°2 au n°3 (n°2 = reason:string)",
                         f"« succès » mais stock = {r.quantity} au lieu de 39 — réponse serveur : {r.message}",
                         BREAKING_SILENT))

        # c) changement de type
        try:
            stub.CalculateFactorial(v1.FactorialRequest(n=5), timeout=3)
            rows.append(_row("CalculateFactorial", "n : int32 -> string", "succès inattendu", "?"))
        except grpc.RpcError as e:
            rows.append(_row("CalculateFactorial", "n : int32 -> string",
                             f"{e.code().name} : {e.details()} (le client avait pourtant envoyé n=5 !)",
                             BREAKING_LOUD + " + message trompeur"))

        # d) RPC renommée
        try:
            list(stub.StreamAnalytics(v1.AnalyticsRequest(metric_name="cpu", count=2), timeout=3))
            rows.append(_row("StreamAnalytics", "RPC renommée -> StreamMetrics", "succès inattendu", "?"))
        except grpc.RpcError as e:
            rows.append(_row("StreamAnalytics", "RPC renommée -> StreamMetrics",
                             f"{e.code().name}", BREAKING_LOUD))
    return rows


def _print_rows(rows: List[Dict[str, str]]) -> None:
    def colour(v):
        if v.startswith(COMPATIBLE):
            return green(v)
        if "SILENCIEUX" in v:
            return red(v)
        return yellow(v)
    for r in rows:
        print(f"• {r['scenario']}")
        print(f"    changement : {r['change']}")
        print(f"    observé    : {r['observed']}")
        print(f"    verdict    : {colour(r['verdict'])}")


def run_contract_demo() -> Dict[str, List[Dict[str, str]]]:
    title("ÉVOLUTION DE CONTRAT — client version N face à un serveur version N+1")

    section("1) Custom RPC (JSON, arguments transmis PAR NOM, aucun contrat écrit)")
    custom_rows = run_custom_rpc_scenarios()
    _print_rows(custom_rows)
    explain("""
En JSON, ce sont les NOMS qui voyagent : renommer un paramètre ou une méthode casse
l'appel. Bonne nouvelle : l'erreur est explicite (INVALID_ARGS, METHOD_NOT_FOUND).
Mauvaise nouvelle : sans contrat écrit, rien ne prévient AVANT l'exécution.""")

    section("2) gRPC (Protobuf binaire, champs transmis PAR NUMÉRO, contrat .proto)")
    print("Le serveur v2 tourne dans un processus séparé (contract_evolution/server_v2.py).")
    grpc_rows = run_grpc_scenarios()
    _print_rows(grpc_rows)
    explain("""
En Protobuf, seuls les NUMÉROS de champ voyagent :
  • renommer un champ ou en AJOUTER un nouveau numéro → compatible ;
  • renuméroter ou changer le type d'un champ → les octets sont mal interprétés,
    souvent SANS erreur : c'est le pire cas (le stock n'a pas bougé, réponse « OK »).
Règles d'or Protobuf : ne jamais réutiliser/changer un numéro, utiliser `reserved`,
versionner le package (inventory.v2) pour les vrais changements cassants.""")

    section("Synthèse")
    all_rows = [("Custom RPC", r) for r in custom_rows] + [("gRPC", r) for r in grpc_rows]
    print(table(["Protocole", "Scénario", "Verdict"],
                [(p, r["scenario"], r["verdict"]) for p, r in all_rows]))
    return {"custom_rpc": custom_rows, "grpc": grpc_rows}
