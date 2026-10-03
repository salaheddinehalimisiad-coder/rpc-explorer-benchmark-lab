"""
Démonstration : pourquoi un appel distant ne doit PAS être traité comme un appel local.

    python main.py --simulate-failures

Scénarios (tous mesurés réellement, latence = latence ARTIFICIELLE de laboratoire) :
  1. Latence injectée : local vs Custom RPC vs gRPC vs REST
  2. Timeout : le serveur est lent, le client abandonne
  3. Serveur éteint : connexion refusée / UNAVAILABLE
  4. Client naïf vs client résilient (retry + backoff) pendant un redémarrage serveur
  5. Le piège du retry sur une opération NON idempotente (stock décrémenté 2 fois)
"""

import statistics
import socket
import threading
import time
from typing import Any, Dict, List

import grpc
import requests

from business.inventory_service import InventoryService
from cli.ui import explain, green, red, section, table, title
from failure_simulator import FailureSimulator
from lab.servers import LabServers, build_custom_server
from rest.rest_client import RestClient, RestClientError
from rpc_core import RPCClient, RPCServer
from rpc_core.resilience import RetryExhaustedError, call_with_retry


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _median_ms(fn, n: int = 5) -> float:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


# 1 ─────────────────────────────────────────────────────────────────────
def scenario_latency(delays_ms=(0, 50, 200)) -> List[Dict[str, Any]]:
    section("1) Latence réseau (artificielle) : local vs distant")
    sim = FailureSimulator()
    local = InventoryService()
    rows = []
    with LabServers(failure_simulator=sim) as lab:
        c, g, r = lab.custom_client(persistent=True), lab.grpc_client(), lab.rest_client()
        for d in delays_ms:
            sim.reset()
            if d:
                sim.enable_latency_spike(d)
            row = {
                "latence_injectee_ms": d,
                "local": _median_ms(lambda: local.calculate_factorial(10)),
                "custom_rpc": _median_ms(lambda: c.calculate_factorial(n=10)),
                "grpc": _median_ms(lambda: g.calculate_factorial(10)),
                "rest": _median_ms(lambda: r.calculate_factorial(10)),
            }
            rows.append(row)
        c.close(); g.close(); r.close()
    print(table(["Latence injectée", "Local", "Custom RPC", "gRPC", "REST"],
                [(f"{x['latence_injectee_ms']} ms", f"{x['local']:.4f} ms", f"{x['custom_rpc']:.2f} ms",
                  f"{x['grpc']:.2f} ms", f"{x['rest']:.2f} ms") for x in rows]))
    print("(médianes de 5 appels — mesures réelles sur cette machine)")
    explain("""
L'appel local ne dépend que du CPU (microsecondes). L'appel distant paie la
sérialisation + le transport, et SUBIT intégralement la latence du réseau :
une boucle de 100 appels à 200 ms = 20 secondes, contre quelques ms en local.""")
    return rows


# 2 ─────────────────────────────────────────────────────────────────────
def scenario_timeout(server_delay_s: float = 1.0, client_timeout_s: float = 0.3) -> List[Dict[str, Any]]:
    section(f"2) Timeout : serveur bloqué {server_delay_s}s, client patient {client_timeout_s}s maximum")
    sim = FailureSimulator()
    sim.simulate_timeout(server_delay_s)
    rows = []
    with LabServers(failure_simulator=sim) as lab:
        attempts = {
            "Custom RPC": lambda: lab.custom_client(timeout=client_timeout_s).calculate_factorial(n=5),
            "gRPC": lambda: lab.grpc_client(timeout=client_timeout_s).calculate_factorial(5),
            "REST": lambda: lab.rest_client(timeout=client_timeout_s).calculate_factorial(5),
        }
        for name, fn in attempts.items():
            t0 = time.perf_counter()
            try:
                fn()
                outcome = "succès (inattendu)"
            except grpc.RpcError as e:
                outcome = f"grpc.RpcError {e.code().name}"
            except Exception as e:  # noqa: BLE001 - on veut afficher le type exact
                outcome = f"{type(e).__name__}: {str(e)[:60]}"
            rows.append({"protocole": name, "erreur": outcome,
                         "attente_ms": (time.perf_counter() - t0) * 1000})
        sim.reset()
    print(table(["Protocole", "Erreur reçue par l'appelant", "Attente réelle"],
                [(x["protocole"], x["erreur"], f"{x['attente_ms']:.0f} ms") for x in rows]))
    explain("""
Sans timeout, l'appelant resterait bloqué indéfiniment. Avec un timeout, il récupère
la main… mais il NE SAIT PAS si le serveur a exécuté l'opération ou non !""")
    return rows


# 3 ─────────────────────────────────────────────────────────────────────
def scenario_server_down() -> List[Dict[str, Any]]:
    section("3) Serveur éteint : personne n'écoute sur le port")
    port = _free_port()
    rows = []
    tests = {
        "Local": lambda: InventoryService().calculate_factorial(5),
        "Custom RPC": lambda: RPCClient(port=port, timeout=1).calculate_factorial(n=5),
        "gRPC": lambda: _grpc_on(port),
        "REST": lambda: RestClient(base_url=f"http://127.0.0.1:{port}", timeout=1).calculate_factorial(5),
    }
    for name, fn in tests.items():
        try:
            res = fn()
            outcome = f"OK → {res}"
        except grpc.RpcError as e:
            outcome = f"grpc.RpcError {e.code().name}"
        except Exception as e:  # noqa: BLE001
            outcome = f"{type(e).__name__}: {str(e)[:70]}"
        rows.append({"protocole": name, "resultat": outcome})
    print(table(["Protocole", "Résultat"], [(x["protocole"], x["resultat"]) for x in rows]))
    explain("""
Une fonction locale ne peut pas être « indisponible ». Une procédure distante, si :
le code appelant DOIT prévoir ce cas (ConnectionError / UNAVAILABLE / HTTP 503).""")
    return rows


def _grpc_on(port: int):
    from grpc_impl.grpc_client import InventoryGRPCClient
    c = InventoryGRPCClient(port=port, timeout=1)
    try:
        return c.calculate_factorial(5)
    finally:
        c.close()


# 4 ─────────────────────────────────────────────────────────────────────
def scenario_retry_on_restart(restart_after_s: float = 0.5) -> Dict[str, Any]:
    section(f"4) Redémarrage serveur ({restart_after_s}s d'indisponibilité) : client naïf vs client résilient")
    port = _free_port()
    service = InventoryService()

    def start_later():
        time.sleep(restart_after_s)
        srv = build_custom_server(service, port=port)
        srv.start()
        holder.append(srv)

    holder: List[RPCServer] = []
    threading.Thread(target=start_later, daemon=True).start()

    client = RPCClient(port=port, timeout=1)
    try:
        client.calculate_factorial(n=5)
        naive = "succès"
    except ConnectionError as e:
        naive = f"CRASH : {type(e).__name__}"
    print(f"Client naïf  : {red(naive)}")

    log = []
    t0 = time.perf_counter()
    try:
        res = call_with_retry(lambda: client.calculate_factorial(n=5), retries=5, base_delay=0.1, backoff=2,
                              on_retry=lambda a, e, d: log.append(f"tentative {a} échouée ({type(e).__name__}), "
                                                                  f"nouvel essai dans {d*1000:.0f} ms"))
        robust = f"succès → {res} après {len(log) + 1} tentative(s), {(time.perf_counter()-t0)*1000:.0f} ms"
    except RetryExhaustedError as e:
        robust = f"échec définitif : {e}"
    for line in log:
        print(f"    {line}")
    print(f"Client résilient : {green(robust)}")
    for srv in holder:
        srv.stop()
    explain("""
Retry + backoff exponentiel = on laisse au serveur le temps de revenir sans le
bombarder. À réserver aux erreurs TRANSITOIRES (réseau), jamais aux erreurs métier.""")
    return {"naive": naive, "robust": robust, "retries_log": log}


# 5 ─────────────────────────────────────────────────────────────────────
class _SlowFirstCall:
    """La 1re exécution prend `delay` secondes (réponse perdue côté client) mais S'EXÉCUTE quand même."""

    def __init__(self, fn, delay: float):
        self.fn, self.delay, self.calls = fn, delay, 0
        self.__name__ = getattr(fn, "__name__", "fn")
        self._lock = threading.Lock()

    def __call__(self, **kwargs):
        with self._lock:
            self.calls += 1
            first = self.calls == 1
        if first:
            time.sleep(self.delay)
        return self.fn(**kwargs)


class _IdempotentStock:
    """Version idempotente : une même `idempotency_key` n'est appliquée qu'une fois."""

    def __init__(self, service: InventoryService):
        self.service = service
        self._seen: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def update_stock(self, item_id: str, quantity_delta: int, idempotency_key: str):
        with self._lock:
            if idempotency_key in self._seen:
                return self._seen[idempotency_key]
            res = self.service.update_stock(item_id, quantity_delta)
            self._seen[idempotency_key] = res
            return res


def scenario_retry_not_idempotent() -> Dict[str, Any]:
    section("5) Piège : retry sur update_stock (opération NON idempotente)")
    results = {}
    for mode in ("naif", "idempotent"):
        service = InventoryService()
        before = service.get_product_details("PROD-005")["stock"]
        server = RPCServer(port=0)
        if mode == "naif":
            server.register_method("update_stock", _SlowFirstCall(service.update_stock, 0.6))
            call = lambda c: c.update_stock(item_id="PROD-005", quantity_delta=-1)  # noqa: E731
        else:
            idem = _IdempotentStock(service)
            server.register_method("update_stock", _SlowFirstCall(idem.update_stock, 0.6))
            call = lambda c: c.update_stock(item_id="PROD-005", quantity_delta=-1,  # noqa: E731
                                            idempotency_key="commande-42")
        server.start()
        client = RPCClient(port=server.port, timeout=0.3)
        call_with_retry(lambda: call(client), retries=3, base_delay=0.4)
        time.sleep(0.4)  # laisse la 1re exécution (lente) se terminer côté serveur
        after = service.get_product_details("PROD-005")["stock"]
        server.stop()
        results[mode] = {"avant": before, "apres": after, "retire": before - after}
    print(table(["Version", "Stock avant", "Stock après", "Unités retirées (attendu : 1)"],
                [("Client naïf + retry", results["naif"]["avant"], results["naif"]["apres"],
                  red(str(results["naif"]["retire"])) if results["naif"]["retire"] != 1 else results["naif"]["retire"]),
                 ("Retry + clé d'idempotence", results["idempotent"]["avant"], results["idempotent"]["apres"],
                  green(str(results["idempotent"]["retire"])))]))
    explain("""
La 1re requête a bien été exécutée par le serveur, mais trop tard : le client avait
déjà abandonné (timeout) et a RÉESSAYÉ → le stock est décrémenté deux fois.
Solution classique : une clé d'idempotence (ID de requête) que le serveur mémorise
pour ne jamais appliquer deux fois la même opération (« exactly-once » simulé).""")
    return results


def run_failure_demo() -> Dict[str, Any]:
    title("LOCAL ≠ DISTANT — simulation de pannes (latence artificielle de laboratoire)")
    return {
        "latency": scenario_latency(),
        "timeout": scenario_timeout(),
        "server_down": scenario_server_down(),
        "retry_restart": scenario_retry_on_restart(),
        "retry_idempotence": scenario_retry_not_idempotent(),
    }
