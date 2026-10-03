"""
Appels SYNCHRONES vs ASYNCHRONES.

    python main.py --async-demo

Chaque appel attend `latency_ms` côté serveur (latence artificielle de laboratoire).
  • Synchrone  : l'appelant attend chaque réponse avant d'envoyer la requête suivante.
  • Asynchrone : l'appelant envoie toutes les requêtes, récupère des « futurs »,
                 puis collecte les résultats ; les attentes se chevauchent.
"""

import time
from typing import Any, Dict, List

from cli.ui import explain, section, table, title
from failure_simulator import FailureSimulator
from lab.servers import LabServers


def run_async_demo(n_calls: int = 5, latency_ms: float = 100.0) -> Dict[str, Any]:
    title(f"SYNCHRONE vs ASYNCHRONE — {n_calls} appels, {latency_ms:.0f} ms de latence par appel")
    sim = FailureSimulator()
    sim.enable_latency_spike(latency_ms)
    values = list(range(1, n_calls + 1))
    rows: List[Dict[str, Any]] = []
    with LabServers(protocols=["custom", "grpc"], failure_simulator=sim) as lab:
        custom = lab.custom_client(timeout=10)
        grpc_client = lab.grpc_client(timeout=10)
        grpc_client.calculate_factorial(1)  # ouvre le canal HTTP/2 avant de mesurer

        def measure(label, protocol, code, fn):
            t0 = time.perf_counter()
            results = fn()
            rows.append({"protocole": protocol, "mode": label, "code": code,
                         "duree_ms": (time.perf_counter() - t0) * 1000, "resultats": results})

        measure("synchrone", "Custom RPC", "for n in …: client.calculate_factorial(n=n)",
                lambda: [custom.calculate_factorial(n=v) for v in values])
        measure("asynchrone", "Custom RPC", "futures = [client.call_async(…)]; f.result()",
                lambda: [f.result() for f in [custom.call_async("calculate_factorial", n=v) for v in values]])
        measure("synchrone", "gRPC", "for n in …: stub.CalculateFactorial(req)",
                lambda: [grpc_client.calculate_factorial(v) for v in values])
        measure("asynchrone", "gRPC", "stub.CalculateFactorial.future(req).result()",
                lambda: [f.result() for f in [grpc_client.calculate_factorial_async(v) for v in values]])
        custom.close()
        grpc_client.close()

    section("Résultats (mesures réelles)")
    print(table(["Protocole", "Mode", "Code côté appelant", "Durée totale", "Résultats"],
                [(r["protocole"], r["mode"], r["code"], f"{r['duree_ms']:.0f} ms", r["resultats"]) for r in rows]))
    explain(f"""
Synchrone : {n_calls} appels × {latency_ms:.0f} ms se succèdent, l'appelant est bloqué pendant chaque attente.
Asynchrone : les {n_calls} requêtes partent sans attendre ; la durée totale ≈ un seul aller-retour.
Les résultats sont identiques : seule l'organisation des attentes change.""")
    return {"n_calls": n_calls, "latency_ms": latency_ms, "rows": rows}
