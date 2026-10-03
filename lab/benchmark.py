"""
Campagne de benchmark comparatif complète (réutilise benchmark.BenchmarkRunner).

    python main.py --benchmark --iterations 1000 --warmup 100

Mesure RÉELLEMENT sur la machine courante :
  • latence (min, moyenne, médiane, p95, p99) et débit pour
    Local / Custom RPC (nouvelle connexion) / Custom RPC (connexion persistante) / gRPC / REST
  • taille des messages sérialisés (JSON vs Protobuf)
  • coût CPU pur de la sérialisation (JSON vs Protobuf)
Les résultats bruts sont enregistrés en JSON dans results/ (non versionné).
"""

import datetime as dt
import json
import os
import platform
import sys
from typing import Any, Dict, List, Optional

from benchmark import BenchmarkRunner
from benchmark.adapters import CustomRPCAdapter, GRPCAdapter, LocalAdapter, RESTAdapter
from cli.ui import explain, section, table, title
from lab.servers import LabServers

OPERATIONS = {
    "calculate_factorial": {"n": 10},
    "get_product_details": {"item_id": "PROD-001"},
}


class _NamedCustomAdapter(CustomRPCAdapter):
    def __init__(self, label: str, **kwargs):
        super().__init__(**kwargs)
        self._label = label

    @property
    def name(self) -> str:
        return self._label


def environment() -> Dict[str, Any]:
    from importlib.metadata import version
    return {
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "grpcio": version("grpcio"),
        "protobuf": version("protobuf"),
        "flask": version("flask"),
        "network": "localhost (127.0.0.1) — pas de vrai réseau",
    }


def run_benchmark(iterations: int = 1000, warmup: int = 100, output_dir: Optional[str] = "results",
                  operations: Optional[List[str]] = None) -> Dict[str, Any]:
    ops = operations or list(OPERATIONS)
    env = environment()
    title(f"BENCHMARK COMPARATIF — {iterations} appels mesurés après {warmup} appels d'échauffement")
    print(table(["Condition", "Valeur"], list(env.items())))

    report: Dict[str, Any] = {"environment": env, "iterations": iterations, "warmup": warmup,
                              "latency": {}, "payload_sizes": None, "serialization": None}
    runner = BenchmarkRunner()
    with LabServers() as lab:
        adapters = [
            LocalAdapter(service=lab.service),
            _NamedCustomAdapter("Custom RPC (1 cnx/appel)", port=lab.custom_port,
                                client=lab.custom_client(persistent=False)),
            _NamedCustomAdapter("Custom RPC (cnx persistante)", port=lab.custom_port,
                                client=lab.custom_client(persistent=True)),
            GRPCAdapter(port=lab.grpc_port, client=lab.grpc_client()),
            RESTAdapter(base_url=f"http://127.0.0.1:{lab.rest_port}", client=lab.rest_client()),
        ]
        for op in ops:
            section(f"Latence — opération {op}({', '.join(f'{k}={v!r}' for k, v in OPERATIONS[op].items())})")
            results = [runner.run_latency_benchmark(a, operation=op, iterations=iterations,
                                                    warmup_iterations=warmup, **OPERATIONS[op])
                       for a in adapters]
            print(table(
                ["Protocole", "Min", "Moyenne", "Médiane", "p95", "p99", "Débit", "Erreurs"],
                [(r.name, f"{r.min_ms:.3f} ms", f"{r.mean_ms:.3f} ms", f"{r.median_ms:.3f} ms",
                  f"{r.p95_ms:.3f} ms", f"{r.p99_ms:.3f} ms", f"{r.throughput_rps:,.0f} req/s",
                  f"{r.error_count}") for r in results]))
            report["latency"][op] = [r.to_dict() for r in results]
        for a in adapters:
            a.close()

    section("Taille des messages sérialisés (corps uniquement)")
    sizes = runner.run_payload_size_comparison()
    rows = []
    for op in ("calculate_factorial", "get_product_details"):
        for proto, s in sizes[op].items():
            rows.append((op, proto, s["request_bytes"], s["response_bytes"], s["total_bytes"]))
    print(table(["Opération", "Protocole", "Requête (o)", "Réponse (o)", "Total (o)"], rows))
    print("NB : n'incluent PAS l'enveloppe de transport (4 o de trame Custom RPC, 5 o de trame gRPC + en-têtes "
          "HTTP/2 compressés, en-têtes HTTP/1.1 texte pour REST). Le message Custom RPC contient aussi un UUID "
          "et un horodatage.")
    report["payload_sizes"] = sizes

    section("Coût CPU de la sérialisation pure (sans réseau)")
    ser = runner.run_serialization_benchmark(iterations=max(iterations, 1000) * 10)
    print(table(["Format", "Encodage", "Décodage", "Total"],
                [("JSON", f"{ser['json']['encode_us']:.2f} µs", f"{ser['json']['decode_us']:.2f} µs",
                  f"{ser['json']['total_us']:.2f} µs"),
                 ("Protobuf", f"{ser['protobuf']['encode_us']:.2f} µs", f"{ser['protobuf']['decode_us']:.2f} µs",
                  f"{ser['protobuf']['total_us']:.2f} µs")]))
    report["serialization"] = ser

    explain("""
Ces chiffres sont des MESURES sur CETTE machine, en localhost : ils ne prouvent rien
d'universel. Pistes d'interprétation (hypothèses à discuter) :
  • « 1 cnx/appel » vs « persistante » : le coût d'ouverture d'une connexion TCP ;
  • gRPC transporte moins d'octets mais sa pile HTTP/2 a un coût fixe par appel ;
  • REST via Flask/werkzeug (serveur de développement) n'est pas optimisé pour la vitesse.""")

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"benchmark_{dt.datetime.now():%Y%m%d_%H%M%S}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nRésultats bruts enregistrés : {path}")
        report["output_file"] = path
    return report
