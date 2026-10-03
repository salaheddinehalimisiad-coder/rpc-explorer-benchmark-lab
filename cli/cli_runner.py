"""
Interface en ligne de commande interactive — « RPC Explorer ».

    python main.py            (ou python main.py --interactive)

Au lancement, les trois serveurs (Custom RPC, gRPC, REST) démarrent en
arrière-plan autour d'un même service métier. Le menu permet ensuite
d'appeler n'importe quelle méthode avec n'importe quel protocole, d'activer
le mode « Sous le capot », d'injecter des pannes sur ces serveurs, puis de
lancer les démonstrations complètes (benchmark, pannes, contrat…).
"""

import json
import time
from typing import Any, Callable, Dict, List, Optional

import grpc

from cli.ui import bold, cyan, dim, green, red, section, title, yellow
from failure_simulator import FailureSimulator
from lab.servers import LabServers
from rest.rest_client import RestClientError
from rpc_core import RPCError
from under_the_hood.protobuf_inspector import GRPCInspectorInterceptor
from under_the_hood.tracer import RPCTracer

METHODS: Dict[str, Dict[str, Any]] = {
    "calculate_factorial": {"n": 5},
    "get_product_details": {"item_id": "PROD-001"},
    "update_stock": {"item_id": "PROD-001", "quantity_delta": -1},
    "stream_analytics": {"metric_name": "cpu_usage", "num_events": 3},
}
PROTOCOLS = ["custom", "grpc", "rest"]
PROTOCOL_LABELS = {"custom": "Custom RPC (JSON / TCP)", "grpc": "gRPC (Protobuf / HTTP/2)",
                   "rest": "REST (JSON / HTTP/1.1)"}


def parse_value(raw: str) -> Any:
    """'5' -> 5, 'true' -> True, 'PROD-001' -> 'PROD-001' (JSON si possible, sinon texte)."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def parse_kv_args(pairs: List[str]) -> Dict[str, Any]:
    out = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Argument invalide '{pair}' (format attendu : nom=valeur)")
        k, v = pair.split("=", 1)
        out[k.strip()] = parse_value(v.strip())
    return out


def invoke(lab_or_clients, protocol: str, method: str, args: Dict[str, Any],
           tracer=None, interceptors=None, timeout: float = 5.0) -> Any:
    """Exécute `method(**args)` via le protocole choisi et retourne le résultat."""
    lab = lab_or_clients
    if protocol == "custom":
        client = lab.custom_client(timeout=timeout, tracer=tracer)
        if method == "stream_analytics":
            return list(client.stream(method, **args))  # vrai flux, trame par trame
        return client.call(method, **args)
    if protocol == "grpc":
        client = lab.grpc_client(timeout=timeout, interceptors=interceptors)
        try:
            if method == "calculate_factorial":
                return client.calculate_factorial(args["n"])
            if method == "get_product_details":
                return client.get_product_details(args["item_id"])
            if method == "update_stock":
                return client.update_stock(args["item_id"], args["quantity_delta"])
            if method == "stream_analytics":
                return list(client.stream_analytics(args["metric_name"], args.get("num_events", 5)))
        finally:
            client.close()
    if protocol == "rest":
        with lab.rest_client(timeout=timeout) as client:
            if method == "calculate_factorial":
                return client.calculate_factorial(args["n"])
            if method == "get_product_details":
                return client.get_product_details(args["item_id"])
            if method == "update_stock":
                return client.update_stock(args["item_id"], args["quantity_delta"])
            if method == "stream_analytics":
                return client.stream_analytics(args["metric_name"], args.get("num_events", 5))
    raise ValueError(f"Protocole '{protocol}' ou méthode '{method}' inconnu(e)")


class CLIRunner:
    """Menu interactif. `input_fn` est injectable pour les tests."""

    def __init__(self, input_fn: Callable[[str], str] = input):
        self.input = input_fn
        self.under_the_hood = False
        self.protocol = "custom"
        self.simulator = FailureSimulator()
        self.tracer = RPCTracer()
        self.lab: Optional[LabServers] = None
        self.history: List[Dict[str, Any]] = []

    # Utilitaires de saisie ----------------------------------------------
    def _ask(self, prompt: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        raw = self.input(f"{prompt}{suffix} : ").strip()
        return raw or default

    def _choose(self, prompt: str, options: List[str], default: int = 1) -> str:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        while True:
            raw = self._ask(prompt, str(default))
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            print(red("  Choix invalide."))

    # Actions du menu ------------------------------------------------------
    def action_call(self):
        section("Appeler une méthode distante")
        self.protocol = self._choose("Protocole", PROTOCOLS, PROTOCOLS.index(self.protocol) + 1)
        method = self._choose("Méthode", list(METHODS))
        args = {}
        for name, default in METHODS[method].items():
            args[name] = parse_value(self._ask(f"  {name}", json.dumps(default) if not isinstance(default, str)
                                               else default))
        self.tracer.clear()
        inspector = GRPCInspectorInterceptor() if self.under_the_hood else None
        t0 = time.perf_counter()
        try:
            result = invoke(self.lab, self.protocol, method, args,
                            tracer=self.tracer if self.under_the_hood else None,
                            interceptors=[inspector] if inspector else None, timeout=2.0)
            status = "OK"
        except (RPCError, RestClientError, ConnectionError, TimeoutError) as e:
            result, status = None, f"{type(e).__name__}: {e}"
        except grpc.RpcError as e:
            result, status = None, f"grpc.RpcError {e.code().name}: {e.details()}"
        elapsed = (time.perf_counter() - t0) * 1000
        if self.under_the_hood:
            section("Sous le capot")
            if self.protocol == "custom" and self.tracer.call_ids():
                self.tracer.display_trace(self.tracer.call_ids()[-1])
            elif self.protocol == "grpc" and inspector and inspector.calls:
                print(GRPCInspectorInterceptor.format_call(inspector.calls[-1]))
            else:
                print(dim("(détail disponible pour Custom RPC et gRPC unaire ; "
                          "pour REST voir le menu « Démo Sous le capot »)"))
        print()
        print(f"{bold('Protocole')} : {PROTOCOL_LABELS[self.protocol]}")
        print(f"{bold('Statut')}    : {green(status) if status == 'OK' else red(status)}")
        print(f"{bold('Résultat')}  : {result!r}")
        print(f"{bold('Durée')}     : {elapsed:.2f} ms (vue par le client)")
        self.history.append({"protocol": self.protocol, "method": method, "args": args,
                             "status": status, "ms": round(elapsed, 3)})

    def action_toggle_under_the_hood(self):
        self.under_the_hood = not self.under_the_hood
        print(f"Mode Sous le capot : {green('ON') if self.under_the_hood else yellow('OFF')}")

    def action_faults(self):
        section("Injecter une panne sur les serveurs du menu")
        choice = self._choose("Panne", ["latence artificielle", "serveur lent (timeout client = 2 s)",
                                        "crash serveur", "tout réinitialiser"], 4)
        self.simulator.reset()
        if choice == "latence artificielle":
            ms = float(self._ask("Latence en ms", "200"))
            self.simulator.enable_latency_spike(ms)
        elif choice.startswith("serveur lent"):
            self.simulator.simulate_timeout(float(self._ask("Le serveur attend (secondes)", "3")))
        elif choice == "crash serveur":
            self.simulator.simulate_server_crash()
        print(f"État du simulateur : {self.simulator.get_status()['active_scenario'] or 'aucune panne'}")
        print(dim("Faites maintenant un appel (menu 1) pour observer l'effet."))

    def action_history(self):
        section("Historique des appels de la session")
        if not self.history:
            print("(vide)")
        for h in self.history:
            print(f"  {h['protocol']:<6} {h['method']:<20} {h['status'][:50]:<50} {h['ms']} ms")

    def run_benchmark_mode(self, iterations: int = 1000):
        from lab.benchmark import run_benchmark
        return run_benchmark(iterations=iterations, warmup=max(10, iterations // 10))

    def run_failure_demo(self):
        from lab.failures import run_failure_demo
        return run_failure_demo()

    # Boucle principale ------------------------------------------------------
    def _menu(self) -> List[tuple]:
        return [
            ("1", "Appeler une méthode (choisir protocole + méthode + arguments)", self.action_call),
            ("2", f"Mode « Sous le capot » : {'ON' if self.under_the_hood else 'OFF'} (basculer)",
             self.action_toggle_under_the_hood),
            ("3", "Injecter / retirer une panne sur ces serveurs", self.action_faults),
            ("4", "Démo Sous le capot comparée (Custom RPC vs gRPC vs REST)", self._demo_uth),
            ("5", "Démo transparence de localisation (local vs RPC vs REST)", self._demo_transparency),
            ("6", "Lancer le benchmark comparatif", self._demo_benchmark),
            ("7", "Démo complète des pannes (local ≠ distant, retry, idempotence)", self.run_failure_demo),
            ("8", "Démo évolution de contrat (v1 vs v2)", self._demo_contract),
            ("9", "Historique des appels", self.action_history),
            ("10", "Démo réponse unique vs streaming", self._demo_streaming),
            ("0", "Quitter", None),
        ]

    def _demo_uth(self):
        from under_the_hood.explorer import run_under_the_hood_demo
        run_under_the_hood_demo(self._choose("Méthode", list(METHODS)))

    def _demo_transparency(self):
        from lab.transparency import run_transparency_demo
        run_transparency_demo()

    def _demo_benchmark(self):
        n = int(self._ask("Nombre d'itérations", "500"))
        self.run_benchmark_mode(n)

    def _demo_streaming(self):
        from lab.streaming import run_streaming_demo
        run_streaming_demo()

    def _demo_contract(self):
        from contract_evolution.demo import run_contract_demo
        run_contract_demo()

    def run_interactive_menu(self):
        self.lab = LabServers(tracer=self.tracer, failure_simulator=self.simulator).start()
        title("RPC EXPLORER & BENCHMARK LAB")
        print("Serveurs démarrés en arrière-plan :")
        print(cyan(self.lab.describe()))
        try:
            while True:
                print()
                for key, label, _ in self._menu():
                    print(f"  {bold(key)}. {label}")
                try:
                    choice = self._ask("\nVotre choix", "0")
                except EOFError:
                    break
                entry = next((m for m in self._menu() if m[0] == choice), None)
                if entry is None:
                    print(red("Choix invalide."))
                    continue
                if entry[2] is None:
                    break
                try:
                    entry[2]()
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print(yellow("\n(interrompu)"))
                except Exception as exc:  # le menu ne doit jamais planter : on affiche l'erreur
                    print(red(f"Erreur : {type(exc).__name__}: {exc}"))
        finally:
            self.lab.stop()
            print("Serveurs arrêtés. Au revoir !")
