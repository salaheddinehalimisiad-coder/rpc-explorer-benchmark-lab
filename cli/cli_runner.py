"""
Lanceur de l'interface en ligne de commande (CLI Runner)

Relie les points d'entrée utilisateur (main.py, menu interactif) aux modules
existants, sans dupliquer leur logique :
- Appels RPC unitaires        -> benchmark.adapters (Local, Custom RPC, gRPC, REST)
- Banc d'essai comparatif     -> benchmark.BenchmarkRunner
- Simulation de pannes        -> failure_simulator.run_failure_demo

Les serveurs Custom RPC, gRPC et REST sont démarrés dans le même processus,
sur 127.0.0.1 avec des ports éphémères (port=0), et partagent une instance
d'InventoryService. Les mesures sont donc des mesures localhost (loopback).
"""

import json
import logging
import platform
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Callable, Dict, List, Optional, Sequence, TextIO

from business.inventory_service import InventoryService
from rpc_core.server_skeleton import RPCServer
from rpc_core.client_stub import RPCClient
from grpc.grpc_server import InventoryGRPCServer
from grpc.grpc_client import InventoryGRPCClient
from rest.rest_server import RestServer
from rest.rest_client import RestClient
from benchmark import (
    BenchmarkRunner,
    BaseBenchmarkAdapter,
    LocalAdapter,
    CustomRPCAdapter,
    GRPCAdapter,
    RESTAdapter,
)
from failure_simulator import run_failure_demo


# Identifiants de protocole acceptés par --protocols et par le menu
PROTOCOLS = ("local", "custom", "grpc", "rest")

# Opérations exposées par le service métier et leurs arguments par défaut
OPERATIONS: Dict[str, Dict[str, Any]] = {
    "calculate_factorial": {"n": 5},
    "get_product_details": {"item_id": "PROD-001"},
    "update_stock": {"item_id": "PROD-002", "quantity_delta": 1},
    "stream_analytics": {"metric_name": "cpu_usage", "count": 5},
}


def parse_protocols(value: Optional[str]) -> List[str]:
    """Convertit 'custom,grpc' en ['custom', 'grpc'] en validant chaque entrée."""
    if not value:
        return list(PROTOCOLS)
    protocols = [p.strip().lower() for p in value.split(",") if p.strip()]
    unknown = [p for p in protocols if p not in PROTOCOLS]
    if unknown:
        raise ValueError(
            f"Protocole(s) inconnu(s) : {unknown}. Valeurs possibles : {list(PROTOCOLS)}"
        )
    return protocols


def collect_environment() -> Dict[str, Any]:
    """Conditions expérimentales à joindre à tout rapport de mesure."""
    versions: Dict[str, Optional[str]] = {}
    for pkg in ("grpcio", "protobuf", "flask", "requests"):
        try:
            versions[pkg] = version(pkg)
        except PackageNotFoundError:
            versions[pkg] = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "libraries": versions,
        "network": "localhost (127.0.0.1), serveurs dans le même processus",
    }


class LabServers:
    """
    Démarre les serveurs Custom RPC, gRPC et REST sur des ports éphémères
    et fournit les adaptateurs correspondants.

    Utilisable comme context manager : les serveurs sont arrêtés en sortie.
    """

    def __init__(
        self,
        protocols: Optional[Sequence[str]] = None,
        failure_simulator: Optional[Any] = None,
        timeout: float = 5.0,
    ):
        self.protocols = list(protocols) if protocols else list(PROTOCOLS)
        self.failure_simulator = failure_simulator
        self.timeout = timeout
        self.service = InventoryService()
        self.adapters: Dict[str, BaseBenchmarkAdapter] = {}
        self._custom_server: Optional[RPCServer] = None
        self._grpc_server: Optional[InventoryGRPCServer] = None
        self._rest_server: Optional[RestServer] = None
        self._werkzeug_level: Optional[int] = None

    def start(self) -> "LabServers":
        # Werkzeug journalise chaque requête HTTP sur stderr : ces écritures
        # pollueraient la sortie et ajouteraient un coût I/O au seul protocole REST.
        werkzeug_logger = logging.getLogger("werkzeug")
        self._werkzeug_level = werkzeug_logger.level
        werkzeug_logger.setLevel(logging.WARNING)
        try:
            if "local" in self.protocols:
                self.adapters["local"] = LocalAdapter(service=self.service)

            if "custom" in self.protocols:
                self._custom_server = RPCServer(
                    host="127.0.0.1", port=0, failure_simulator=self.failure_simulator
                )
                for name in OPERATIONS:
                    self._custom_server.register_method(name, getattr(self.service, name))
                self._custom_server.start(threaded=True)
                self.adapters["custom"] = CustomRPCAdapter(
                    client=RPCClient(
                        host="127.0.0.1", port=self._custom_server.port, timeout=self.timeout
                    )
                )

            if "grpc" in self.protocols:
                self._grpc_server = InventoryGRPCServer(
                    host="127.0.0.1",
                    port=0,
                    service=self.service,
                    failure_simulator=self.failure_simulator,
                )
                grpc_port = self._grpc_server.start()
                self.adapters["grpc"] = GRPCAdapter(
                    client=InventoryGRPCClient(
                        host="127.0.0.1", port=grpc_port, timeout=self.timeout
                    )
                )

            if "rest" in self.protocols:
                self._rest_server = RestServer(
                    host="127.0.0.1",
                    port=0,
                    service=self.service,
                    failure_simulator=self.failure_simulator,
                )
                rest_port = self._rest_server.start(threaded=True)
                self.adapters["rest"] = RESTAdapter(
                    client=RestClient(
                        base_url=f"http://127.0.0.1:{rest_port}", timeout=self.timeout
                    )
                )
        except BaseException:
            self.stop()
            raise
        return self

    def stop(self) -> None:
        for adapter in self.adapters.values():
            adapter.close()
        self.adapters.clear()
        if self._custom_server is not None:
            self._custom_server.stop()
            self._custom_server = None
        if self._grpc_server is not None:
            self._grpc_server.stop(grace=0.1)
            self._grpc_server = None
        if self._rest_server is not None:
            self._rest_server.stop()
            self._rest_server = None
        if self._werkzeug_level is not None:
            logging.getLogger("werkzeug").setLevel(self._werkzeug_level)
            self._werkzeug_level = None

    def __enter__(self) -> "LabServers":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


class CLIRunner:
    """
    Gestionnaire d'interface console et interactive.

    Args:
        out: Flux de sortie (par défaut sys.stdout).
        input_func: Fonction de saisie (par défaut input), injectable pour les tests.
    """

    def __init__(
        self,
        out: Optional[TextIO] = None,
        input_func: Callable[[str], str] = input,
    ):
        self.out = out if out is not None else sys.stdout
        self.input_func = input_func

    def _print(self, text: str = "") -> None:
        print(text, file=self.out)

    # ─────────────────────────────────────────────────────────────────────
    # Appel unitaire
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def call_operation(
        adapter: BaseBenchmarkAdapter, operation: str, args: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Exécute une opération métier via l'adaptateur (même routage que le benchmark)."""
        if operation not in OPERATIONS:
            raise ValueError(
                f"Opération '{operation}' inconnue. Valeurs possibles : {list(OPERATIONS)}"
            )
        call_args = dict(OPERATIONS[operation])
        call_args.update(args or {})
        result = BenchmarkRunner()._dispatch_call(adapter, operation, **call_args)
        # Le flux gRPC est un itérateur : on le matérialise pour l'affichage
        if not isinstance(result, (dict, list, str, int, float, bool, type(None))):
            result = list(result)
        return result

    # ─────────────────────────────────────────────────────────────────────
    # Benchmark
    # ─────────────────────────────────────────────────────────────────────

    def run_benchmark_mode(
        self,
        iterations: int = 1000,
        warmup_iterations: int = 50,
        protocols: Optional[Sequence[str]] = None,
        operation: str = "calculate_factorial",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lance le banc de test comparatif : latence par protocole, taille des
        payloads sérialisés et micro-benchmark de sérialisation.

        Returns:
            Le rapport complet (dict sérialisable JSON).
        """
        if iterations < 1:
            raise ValueError("iterations doit être >= 1")
        if warmup_iterations < 0:
            raise ValueError("warmup doit être >= 0")
        if operation not in OPERATIONS:
            raise ValueError(
                f"Opération '{operation}' inconnue. Valeurs possibles : {list(OPERATIONS)}"
            )
        selected = list(protocols) if protocols else list(PROTOCOLS)

        environment = collect_environment()
        self._print("=" * 80)
        self._print(" BENCHMARK COMPARATIF — RPC Explorer & Benchmark Lab")
        self._print("=" * 80)
        self._print(f"Opération     : {operation} {OPERATIONS[operation]}")
        self._print(f"Protocoles    : {', '.join(selected)}")
        self._print(f"Itérations    : {iterations} (warm-up : {warmup_iterations})")
        self._print(f"Environnement : Python {environment['python']} — {environment['os']}")
        self._print(f"Réseau        : {environment['network']}")
        self._print()

        runner = BenchmarkRunner()
        results = []
        with LabServers(protocols=selected) as lab:
            for proto in selected:
                adapter = lab.adapters[proto]
                self._print(f"[BENCHMARK] {adapter.name} ...")
                results.append(
                    runner.run_latency_benchmark(
                        adapter=adapter,
                        operation=operation,
                        iterations=iterations,
                        warmup_iterations=warmup_iterations,
                        **OPERATIONS[operation],
                    )
                )

        payloads = runner.run_payload_size_comparison()
        serialization = runner.run_serialization_benchmark(iterations=iterations)

        self._print()
        self._print("--- Latence (mesurée côté client, en ms) ---")
        self._print(BenchmarkRunner.format_comparison_table(results))
        for r in results:
            if r.error_count:
                self._print(
                    f"[ERREURS] {r.name} : {r.error_count}/{r.iterations} appels en échec "
                    f"({r.error_rate:.1f} %)"
                )

        self._print()
        self._print("--- Taille des payloads sérialisés (octets, corps uniquement) ---")
        for op in ("calculate_factorial", "get_product_details"):
            for proto_name, sizes in payloads[op].items():
                self._print(
                    f"{op:<22} {proto_name:<11} requête={sizes['request_bytes']:>4} "
                    f"réponse={sizes['response_bytes']:>4} total={sizes['total_bytes']:>4}"
                )

        self._print()
        self._print(f"--- Sérialisation pure ({serialization['iterations']} itérations, µs/op) ---")
        for fmt in ("json", "protobuf"):
            s = serialization[fmt]
            self._print(
                f"{fmt:<9} encode={s['encode_us']:.3f} decode={s['decode_us']:.3f} "
                f"total={s['total_us']:.3f}"
            )

        self._print()
        self._print(
            "Ces mesures ne valent que pour cette machine et cette configuration "
            "(localhost, un seul processus)."
        )

        report = {
            "conditions": {
                "operation": operation,
                "arguments": OPERATIONS[operation],
                "protocols": selected,
                "iterations": iterations,
                "warmup_iterations": warmup_iterations,
                "concurrency": 1,
                "environment": environment,
            },
            "latency_comparison": {r.name: r.to_dict() for r in results},
            "payload_sizes": payloads,
            "serialization_microbenchmark": serialization,
        }

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self._print(f"Rapport JSON écrit dans : {output_path}")

        return report

    # ─────────────────────────────────────────────────────────────────────
    # Simulation de pannes
    # ─────────────────────────────────────────────────────────────────────

    def run_failure_demo(
        self,
        iterations: int = 30,
        delays: Sequence[float] = (0.0, 50.0, 100.0),
        timeout_delay_seconds: float = 1.0,
        client_timeout: float = 0.2,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lance la démonstration complète des pannes (latence, timeout, crash,
        isolation) via failure_simulator.run_failure_demo.
        """
        self._print("=" * 80)
        self._print(" SIMULATION DE PANNES — latence artificielle de laboratoire")
        self._print("=" * 80)
        results = run_failure_demo.run_all_experiments(
            iterations=iterations,
            delays=delays,
            timeout_delay_seconds=timeout_delay_seconds,
            client_timeout=client_timeout,
            output_path=output_path,
        )
        if output_path:
            self._print(f"Résultats JSON écrits dans : {output_path}")
        return results

    def run_latency_demo(self, latency_ms: float, iterations: int = 30) -> Dict[str, Any]:
        """Compare la baseline (0 ms) à une latence artificielle donnée sur les 3 protocoles."""
        if latency_ms < 0:
            raise ValueError("La latence doit être >= 0 ms")
        self._print(f"[LATENCE ARTIFICIELLE] {latency_ms:.0f} ms injectés côté serveur")
        delays = [0.0] if latency_ms == 0 else [0.0, float(latency_ms)]
        return run_failure_demo.run_latency_experiment(delays=delays, iterations=iterations)

    def run_timeout_demo(
        self, failure_delay_seconds: float, client_timeout: float = 1.0
    ) -> Dict[str, Any]:
        """Le serveur retient sa réponse ; le client abandonne au bout de client_timeout."""
        if failure_delay_seconds <= 0 or client_timeout <= 0:
            raise ValueError("Les délais doivent être > 0")
        self._print(
            f"[TIMEOUT] Réponse serveur retardée de {failure_delay_seconds}s, "
            f"timeout client {client_timeout}s"
        )
        return run_failure_demo.run_timeout_experiment(
            failure_delay_seconds=failure_delay_seconds, client_timeout=client_timeout
        )

    # ─────────────────────────────────────────────────────────────────────
    # Menu interactif
    # ─────────────────────────────────────────────────────────────────────

    def _ask(self, prompt: str, default: str = "") -> str:
        try:
            answer = self.input_func(prompt).strip()
        except EOFError:
            return "0"
        return answer or default

    def _ask_int(self, prompt: str, default: int) -> int:
        raw = self._ask(f"{prompt} [{default}] : ", str(default))
        try:
            return int(raw)
        except ValueError:
            self._print(f"Valeur invalide '{raw}', utilisation de {default}.")
            return default

    def _interactive_call(self, lab: LabServers) -> None:
        self._print("Protocoles : " + ", ".join(PROTOCOLS))
        proto = self._ask("Protocole [custom] : ", "custom").lower()
        if proto not in lab.adapters:
            self._print(f"[ERREUR] Protocole inconnu : {proto}")
            return
        self._print("Opérations : " + ", ".join(OPERATIONS))
        operation = self._ask("Opération [calculate_factorial] : ", "calculate_factorial")
        if operation not in OPERATIONS:
            self._print(f"[ERREUR] Opération inconnue : {operation}")
            return
        raw_args = self._ask(
            f"Arguments JSON [{json.dumps(OPERATIONS[operation])}] : ", "{}"
        )
        try:
            args = json.loads(raw_args)
            if not isinstance(args, dict):
                raise ValueError("un objet JSON est attendu")
        except ValueError as err:
            self._print(f"[ERREUR] Arguments invalides : {err}")
            return

        adapter = lab.adapters[proto]
        t0 = time.perf_counter()
        try:
            result = self.call_operation(adapter, operation, args)
        except Exception as err:  # l'erreur est affichée, pas masquée
            elapsed = (time.perf_counter() - t0) * 1000.0
            self._print(
                f"[{adapter.name}] {operation} -> ÉCHEC après {elapsed:.3f} ms : "
                f"{type(err).__name__}: {err}"
            )
            return
        elapsed = (time.perf_counter() - t0) * 1000.0
        self._print(f"[{adapter.name}] {operation} -> OK en {elapsed:.3f} ms")
        self._print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    def run_interactive_menu(self) -> None:
        """Lance le menu interactif textuel."""
        menu = (
            "\n--- RPC Explorer ---\n"
            "1. Appel unitaire (choix du protocole et de la méthode)\n"
            "2. Benchmark comparatif\n"
            "3. Simulation de pannes\n"
            "0. Quitter"
        )
        with LabServers() as lab:
            while True:
                self._print(menu)
                choice = self._ask("Choix : ", "0")
                if choice == "0":
                    self._print("Au revoir.")
                    return
                if choice == "1":
                    self._interactive_call(lab)
                elif choice == "2":
                    iterations = self._ask_int("Itérations", 200)
                    warmup = self._ask_int("Warm-up", 20)
                    self.run_benchmark_mode(iterations=iterations, warmup_iterations=warmup)
                elif choice == "3":
                    iterations = self._ask_int("Itérations par scénario de latence", 30)
                    self.run_failure_demo(iterations=iterations)
                else:
                    self._print(f"Choix invalide : {choice}")
