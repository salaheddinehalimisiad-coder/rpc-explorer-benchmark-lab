#!/usr/bin/env python3
"""
Campagne de benchmark comparatif réel (Phase 08) : Local vs Custom RPC vs gRPC vs REST.

Démarre les trois serveurs sur 127.0.0.1 (ports éphémères), puis mesure :
1. Latence séquentielle (min, moyenne, p50, p90, p95, p99, max, écart-type)
   pour les 4 opérations métier, avec warm-up et plusieurs répétitions
   (l'ordre des protocoles est permuté à chaque répétition).
2. Débit sous charge concurrente (1 client par thread, niveaux configurables).
3. Octets réellement transmis sur le fil (TCP payload, dans les deux sens),
   mesurés par un proxy TCP de comptage intercalé entre client et serveur.
4. Micro-benchmark de sérialisation JSON vs Protobuf (moteur existant).

Toutes les valeurs écrites dans le fichier JSON de sortie sont des mesures
réelles de l'exécution courante. Aucune valeur n'est saisie à la main.

Usage :
    python -m benchmark.run_comparative_benchmark
    python -m benchmark.run_comparative_benchmark --iterations 2000 --warmup 200 \
        --repetitions 3 --output docs/benchmark/phase08_raw_results.json
"""

import argparse
import json
import logging
import multiprocessing
import os
import platform
import select
import socket
import sys
import threading
import time
from concurrent import futures
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Callable, Dict, List

from business.inventory_service import InventoryService
from rpc_core.server_skeleton import RPCServer
from rpc_core.client_stub import RPCClient
from grpc.grpc_server import InventoryGRPCServer
from grpc.grpc_client import InventoryGRPCClient
from rest.rest_server import RestServer
from rest.rest_client import RestClient

from benchmark.adapters import (
    BaseBenchmarkAdapter,
    LocalAdapter,
    CustomRPCAdapter,
    GRPCAdapter,
    RESTAdapter,
)
from benchmark.benchmark_runner import BenchmarkRunner
from benchmark.metrics import BenchmarkResult


HOST = "127.0.0.1"

# Paramètres d'appel identiques pour tous les protocoles (règle de comparabilité).
OPERATIONS: Dict[str, Dict[str, Any]] = {
    "calculate_factorial": {"n": 5},
    "get_product_details": {"item_id": "PROD-001"},
    "update_stock": {"item_id": "PROD-002", "quantity_delta": 1},
    "stream_analytics": {"metric_name": "cpu_usage", "count": 5},
}


# ─────────────────────────────────────────────────────────────────────────────
# Proxy TCP de comptage d'octets (mesure "sur le fil")
# ─────────────────────────────────────────────────────────────────────────────

class ByteCountingProxy:
    """
    Proxy TCP transparent qui relaie les octets entre un client et un serveur
    et compte le volume transmis dans chaque sens ainsi que le nombre de
    connexions TCP ouvertes. Compte la charge utile TCP (couche application :
    framing, en-têtes HTTP, trames HTTP/2), pas les en-têtes TCP/IP.
    """

    def __init__(self, target_host: str, target_port: int):
        self.target = (target_host, target_port)
        self._lock = threading.Lock()
        self.client_to_server = 0
        self.server_to_client = 0
        self.connections = 0
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((HOST, 0))
        self._listener.listen(128)
        self.port = self._listener.getsockname()[1]
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return {
                "client_to_server": self.client_to_server,
                "server_to_client": self.server_to_client,
                "connections": self.connections,
            }

    def _accept_loop(self):
        while self._running:
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            try:
                upstream = socket.create_connection(self.target)
            except OSError:
                client.close()
                continue
            with self._lock:
                self.connections += 1
            threading.Thread(target=self._pump, args=(client, upstream), daemon=True).start()

    def _pump(self, client: socket.socket, upstream: socket.socket):
        socks = [client, upstream]
        try:
            while True:
                readable, _, _ = select.select(socks, [], [], 1.0)
                if not self._running:
                    return
                for s in readable:
                    data = s.recv(65536)
                    if not data:
                        return
                    if s is client:
                        upstream.sendall(data)
                        with self._lock:
                            self.client_to_server += len(data)
                    else:
                        client.sendall(data)
                        with self._lock:
                            self.server_to_client += len(data)
        except OSError:
            return
        finally:
            client.close()
            upstream.close()

    def close(self):
        self._running = False
        self._listener.close()


# ─────────────────────────────────────────────────────────────────────────────
# Environnement expérimental
# ─────────────────────────────────────────────────────────────────────────────

def collect_environment() -> Dict[str, Any]:
    def version(pkg: str) -> str:
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            return "non installé"

    cpu_model = platform.processor() or "inconnu"
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass

    mem_total_mb = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    mem_total_mb = int(line.split()[1]) // 1024
                    break
    except OSError:
        pass

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "logical_cpus": os.cpu_count(),
        "ram_total_mb": mem_total_mb,
        "python": platform.python_version(),
        "libraries": {
            pkg: version(pkg)
            for pkg in ("grpcio", "protobuf", "flask", "werkzeug", "requests")
        },
        "network": "loopback 127.0.0.1 (même machine)",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Infrastructure : serveurs et fabriques de clients
# ─────────────────────────────────────────────────────────────────────────────

def _start_server(kind: str):
    """Construit et démarre un serveur ; retourne (objet serveur, port effectif)."""
    service = InventoryService()
    if kind == "Custom RPC":
        server = RPCServer(host=HOST, port=0)
        for name in OPERATIONS:
            server.register_method(name, getattr(service, name))
        server.start()
        return server, server.port
    if kind == "gRPC":
        server = InventoryGRPCServer(host=HOST, port=0, service=service)
        return server, server.start()
    if kind == "REST":
        server = RestServer(host=HOST, port=0, service=service)
        return server, server.start(threaded=True)
    raise ValueError(f"Serveur inconnu : {kind}")


def _stop_server(kind: str, server):
    if kind == "gRPC":
        server.stop(grace=0.1)
    else:
        server.stop()


def _server_process_main(kind: str, conn):
    """Point d'entrée d'un processus serveur dédié (mode par défaut)."""
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server, port = _start_server(kind)
    conn.send(port)
    conn.recv()  # bloque jusqu'à l'ordre d'arrêt
    _stop_server(kind, server)


class LabServers:
    """
    Démarre les trois serveurs, chacun avec sa propre instance du service métier.

    Par défaut chaque serveur tourne dans son propre processus Python : le client
    et le serveur ne partagent ni le GIL ni l'ordonnanceur de threads, comme dans
    un vrai déploiement distribué. `in_process=True` reproduit l'ancien montage
    (tout dans un seul processus, comme dans tests/test_benchmark.py).
    """

    KINDS = ("Custom RPC", "gRPC", "REST")

    def __init__(self, in_process: bool = False):
        self.in_process = in_process
        self.local_service = InventoryService()
        self._handles: Dict[str, Any] = {}
        self.ports: Dict[str, int] = {}

    def start(self):
        ctx = multiprocessing.get_context("spawn")
        for kind in self.KINDS:
            if self.in_process:
                server, port = _start_server(kind)
                self._handles[kind] = server
            else:
                parent_conn, child_conn = ctx.Pipe()
                proc = ctx.Process(target=_server_process_main, args=(kind, child_conn), daemon=True)
                proc.start()
                if not parent_conn.poll(30):
                    raise RuntimeError(f"Le processus serveur {kind} n'a pas démarré.")
                port = parent_conn.recv()
                self._handles[kind] = (proc, parent_conn)
            self.ports[kind] = port
        self.custom_port = self.ports["Custom RPC"]
        self.grpc_port = self.ports["gRPC"]
        self.rest_port = self.ports["REST"]

    def stop(self):
        for kind, handle in self._handles.items():
            if self.in_process:
                _stop_server(kind, handle)
            else:
                proc, conn = handle
                conn.send("stop")
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.terminate()

    def factories(self, ports: Dict[str, int] = None) -> Dict[str, Callable[[], BaseBenchmarkAdapter]]:
        """Fabriques d'adaptateurs ; `ports` permet de rediriger vers un proxy."""
        ports = ports or {
            "Custom RPC": self.custom_port,
            "gRPC": self.grpc_port,
            "REST": self.rest_port,
        }
        return {
            "Local": lambda: LocalAdapter(service=self.local_service),
            "Custom RPC": lambda: CustomRPCAdapter(client=RPCClient(host=HOST, port=ports["Custom RPC"])),
            "gRPC": lambda: GRPCAdapter(client=InventoryGRPCClient(host=HOST, port=ports["gRPC"])),
            "REST": lambda: RESTAdapter(client=RestClient(base_url=f"http://{HOST}:{ports['REST']}")),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Campagnes de mesure
# ─────────────────────────────────────────────────────────────────────────────

def run_latency_campaign(factories, runner: BenchmarkRunner, iterations: int,
                         warmup: int, repetitions: int) -> Dict[str, Any]:
    """Latence séquentielle (1 client) pour chaque opération et chaque protocole."""
    protocols = list(factories.keys())
    per_rep: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    pooled_latencies: Dict[str, Dict[str, List[float]]] = {}
    pooled_meta: Dict[str, Dict[str, Dict[str, float]]] = {}

    for rep in range(repetitions):
        # Rotation de l'ordre des protocoles pour limiter le biais d'ordre.
        order = protocols[rep % len(protocols):] + protocols[:rep % len(protocols)]
        for operation, kwargs in OPERATIONS.items():
            for proto in order:
                adapter = factories[proto]()
                try:
                    res = runner.run_latency_benchmark(
                        adapter=adapter,
                        operation=operation,
                        iterations=iterations,
                        warmup_iterations=warmup,
                        **kwargs,
                    )
                finally:
                    adapter.close()
                print(f"  rep {rep + 1}/{repetitions} {res.summary_str()} | errors: {res.error_count}")
                per_rep.setdefault(operation, {}).setdefault(proto, []).append(res.to_dict())
                pooled_latencies.setdefault(operation, {}).setdefault(proto, []).extend(res.latencies_ms)
                meta = pooled_meta.setdefault(operation, {}).setdefault(
                    proto, {"total_time": 0.0, "errors": 0})
                meta["total_time"] += res.total_time_seconds
                meta["errors"] += res.error_count

    pooled: Dict[str, Dict[str, Any]] = {}
    for operation, by_proto in pooled_latencies.items():
        for proto, lats in by_proto.items():
            meta = pooled_meta[operation][proto]
            result = BenchmarkResult(
                name=proto,
                operation=operation,
                latencies_ms=lats,
                total_time_seconds=meta["total_time"],
                warmup_iterations=warmup * repetitions,
                error_count=int(meta["errors"]),
            )
            pooled.setdefault(operation, {})[proto] = result.to_dict()

    return {"pooled": pooled, "per_repetition": per_rep}


def run_concurrency_campaign(factories, levels: List[int], per_worker: int,
                             warmup: int) -> Dict[str, Any]:
    """
    Débit sous charge : `workers` threads, chacun avec son propre client
    (pas de partage de session HTTP ni de canal entre threads).
    """
    results: Dict[str, Dict[str, Any]] = {}
    runner = BenchmarkRunner()
    for proto, factory in factories.items():
        if proto == "Local":
            continue
        for workers in levels:
            adapters = [factory() for _ in range(workers)]
            for adp in adapters:
                for _ in range(warmup):
                    runner._dispatch_call(adp, "calculate_factorial", n=5)

            barrier = threading.Barrier(workers)
            error_types: Dict[str, int] = {}
            errors_lock = threading.Lock()

            def worker(adp: BaseBenchmarkAdapter):
                lats: List[float] = []
                errs = 0
                barrier.wait()
                for _ in range(per_worker):
                    t0 = time.perf_counter()
                    try:
                        adp.call_calculate_factorial(5)
                        lats.append((time.perf_counter() - t0) * 1000.0)
                    except Exception as exc:  # comptées et typées, jamais masquées
                        errs += 1
                        with errors_lock:
                            key = type(exc).__name__
                            error_types[key] = error_types.get(key, 0) + 1
                return lats, errs

            all_lats: List[float] = []
            total_errors = 0
            t_start = time.perf_counter()
            with futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for lats, errs in pool.map(worker, adapters):
                    all_lats.extend(lats)
                    total_errors += errs
            elapsed = time.perf_counter() - t_start
            for adp in adapters:
                adp.close()

            res = BenchmarkResult(
                name=proto, operation="calculate_factorial", latencies_ms=all_lats,
                total_time_seconds=elapsed, warmup_iterations=warmup,
                error_count=total_errors, concurrency=workers,
            )
            entry = res.to_dict()
            entry["error_types"] = error_types
            results.setdefault(proto, {})[str(workers)] = entry
            print(f"  c={workers:<3} {res.summary_str()} | errors: {total_errors} {error_types or ''}")
    return results


def run_wire_bytes_campaign(servers: LabServers, calls: int) -> Dict[str, Any]:
    """
    Octets réellement échangés sur TCP, par appel, via un proxy de comptage.
    Le premier appel (ouverture de connexion, préface HTTP/2, SETTINGS...) est
    mesuré séparément du régime établi.
    """
    proxies = {
        "Custom RPC": ByteCountingProxy(HOST, servers.custom_port),
        "gRPC": ByteCountingProxy(HOST, servers.grpc_port),
        "REST": ByteCountingProxy(HOST, servers.rest_port),
    }
    factories = servers.factories({name: p.port for name, p in proxies.items()})
    runner = BenchmarkRunner()
    results: Dict[str, Dict[str, Any]] = {}

    def settle():
        time.sleep(0.05)  # laisse les threads du proxy relayer les derniers octets

    try:
        for operation, kwargs in OPERATIONS.items():
            for proto, proxy in proxies.items():
                adapter = factories[proto]()
                try:
                    s0 = proxy.snapshot()
                    runner._dispatch_call(adapter, operation, **kwargs)
                    settle()
                    s1 = proxy.snapshot()
                    for _ in range(calls):
                        runner._dispatch_call(adapter, operation, **kwargs)
                    settle()
                    s2 = proxy.snapshot()
                finally:
                    adapter.close()
                results.setdefault(operation, {})[proto] = {
                    "first_call": {
                        "request_bytes": s1["client_to_server"] - s0["client_to_server"],
                        "response_bytes": s1["server_to_client"] - s0["server_to_client"],
                        "tcp_connections_opened": s1["connections"] - s0["connections"],
                    },
                    "steady_state_per_call": {
                        "calls_measured": calls,
                        "request_bytes": round((s2["client_to_server"] - s1["client_to_server"]) / calls, 2),
                        "response_bytes": round((s2["server_to_client"] - s1["server_to_client"]) / calls, 2),
                        "total_bytes": round(
                            ((s2["client_to_server"] - s1["client_to_server"])
                             + (s2["server_to_client"] - s1["server_to_client"])) / calls, 2),
                        "tcp_connections_opened": s2["connections"] - s1["connections"],
                    },
                }
                ss = results[operation][proto]["steady_state_per_call"]
                print(f"  {operation:<22} {proto:<11} req {ss['request_bytes']:>8} B | "
                      f"resp {ss['response_bytes']:>8} B | conns {ss['tcp_connections_opened']}")
    finally:
        for p in proxies.values():
            p.close()
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark comparatif réel Local / Custom RPC / gRPC / REST")
    parser.add_argument("--iterations", type=int, default=2000, help="Appels mesurés par (opération, protocole, répétition)")
    parser.add_argument("--warmup", type=int, default=200, help="Appels de chauffe non mesurés")
    parser.add_argument("--repetitions", type=int, default=3, help="Répétitions de la campagne de latence")
    parser.add_argument("--concurrency", type=str, default="1,4,8,16", help="Niveaux de concurrence (threads)")
    parser.add_argument("--per-worker", type=int, default=250, help="Appels mesurés par thread en concurrence")
    parser.add_argument("--wire-calls", type=int, default=200, help="Appels pour la mesure d'octets sur le fil")
    parser.add_argument("--in-process", action="store_true",
                        help="Serveurs dans le même processus que le client (GIL partagé)")
    parser.add_argument("--output", type=str, default="docs/benchmark/phase08_raw_results.json")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    levels = [int(x) for x in args.concurrency.split(",") if x.strip()]
    config = {
        "iterations": args.iterations,
        "warmup": args.warmup,
        "repetitions": args.repetitions,
        "concurrency_levels": levels,
        "per_worker": args.per_worker,
        "wire_calls": args.wire_calls,
        "operations": OPERATIONS,
        "artificial_latency_ms": 0,
        "failure_simulator": "désactivé",
        "werkzeug_request_log": "désactivé (niveau ERROR)",
        "server_placement": "même processus que le client" if args.in_process
        else "un processus Python dédié par serveur",
    }

    # Le serveur de développement Werkzeug écrit une ligne sur stderr par requête.
    # Cette E/S console n'existe pas côté Custom RPC ni gRPC : on la coupe pour
    # mesurer le middleware et non le terminal (documenté dans la synthèse).
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    servers = LabServers(in_process=args.in_process)
    servers.start()
    report: Dict[str, Any] = {"environment": collect_environment(), "config": config}
    try:
        runner = BenchmarkRunner()
        factories = servers.factories()

        print("[BENCHMARK] 1/4 Latence séquentielle")
        report["latency"] = run_latency_campaign(
            factories, runner, args.iterations, args.warmup, args.repetitions)

        print("[BENCHMARK] 2/4 Débit sous concurrence (calculate_factorial)")
        report["concurrency"] = run_concurrency_campaign(
            factories, levels, args.per_worker, warmup=20)

        print("[BENCHMARK] 3/4 Octets sur le fil (proxy TCP de comptage)")
        report["wire_bytes"] = run_wire_bytes_campaign(servers, args.wire_calls)

        print("[BENCHMARK] 4/4 Sérialisation JSON vs Protobuf et tailles de messages")
        report["serialization_microbenchmark"] = runner.run_serialization_benchmark(iterations=10000)
        report["serialized_message_sizes"] = runner.run_payload_size_comparison()
    finally:
        servers.stop()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"[BENCHMARK] Résultats bruts écrits dans {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
