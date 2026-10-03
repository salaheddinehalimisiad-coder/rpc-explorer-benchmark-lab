#!/usr/bin/env python3
"""
Point d'entrée principal : RPC Explorer & Benchmark Lab

    python main.py                         menu interactif (serveurs lancés automatiquement)
    python main.py --dashboard             tableau de bord web dans le navigateur
    python main.py --demo                  démonstration complète, dans l'ordre pédagogique
    python main.py --under-the-hood        cycle d'un appel observé sur les 3 protocoles
    python main.py --transparency-demo     appel local vs Custom RPC vs gRPC vs REST
    python main.py --benchmark             banc d'essai comparatif (--iterations, --warmup)
    python main.py --simulate-failures     latence, timeout, panne, retry, idempotence
    python main.py --contract-demo         évolution de contrat (client v1 / serveur v2)
    python main.py --streaming-demo        réponse unique vs streaming (Custom RPC)

Mode « vrai réseau » (deux terminaux, voire deux machines) :
    python main.py --serve all --trace                           # terminal 1
    python main.py --call custom calculate_factorial n=5 --trace # terminal 2
"""

import argparse
import json
import sys

VERSION = "RPC Explorer & Benchmark Lab v1.3.0"
DEFAULT_PORTS = {"custom": 5000, "grpc": 50051, "rest": 5001}


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="RPC Explorer & Benchmark Lab — démonstrateur pédagogique des Remote Procedure Calls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    modes = parser.add_argument_group("modes")
    modes.add_argument("--interactive", action="store_true", help="menu interactif (mode par défaut)")
    modes.add_argument("--demo", action="store_true", help="démonstration complète enchaînée")
    modes.add_argument("--under-the-hood", action="store_true", help="observer le cycle complet d'un appel")
    modes.add_argument("--transparency-demo", action="store_true", help="transparence de localisation")
    modes.add_argument("--benchmark", action="store_true", help="banc d'essai comparatif")
    modes.add_argument("--simulate-failures", action="store_true", help="démonstration des pannes")
    modes.add_argument("--contract-demo", action="store_true", help="évolution de contrat v1/v2")
    modes.add_argument("--streaming-demo", action="store_true", help="réponse unique vs streaming")
    modes.add_argument("--dashboard", action="store_true",
                       help="tableau de bord web local (http://127.0.0.1:8080 par défaut, --port pour changer)")
    modes.add_argument("--serve", choices=["custom", "grpc", "rest", "all"],
                       help="lancer un serveur au premier plan (Ctrl+C pour arrêter)")
    modes.add_argument("--call", nargs="+", metavar=("PROTOCOLE METHODE", "nom=valeur"),
                       help="appeler un serveur déjà lancé : --call custom calculate_factorial n=5")

    opts = parser.add_argument_group("options")
    opts.add_argument("--iterations", type=int, default=1000, help="benchmark : appels mesurés (défaut 1000)")
    opts.add_argument("--warmup", type=int, default=100, help="benchmark : appels d'échauffement (défaut 100)")
    opts.add_argument("--no-save", action="store_true", help="benchmark : ne pas écrire results/*.json")
    opts.add_argument("--method", default="calculate_factorial",
                      choices=["calculate_factorial", "get_product_details", "update_stock", "stream_analytics"],
                      help="--under-the-hood : méthode à observer")
    opts.add_argument("--args", nargs="*", default=None, metavar="nom=valeur",
                      help="--under-the-hood : arguments de la méthode")
    opts.add_argument("--host", default="127.0.0.1", help="--serve / --call : adresse (défaut 127.0.0.1)")
    opts.add_argument("--port", type=int, default=None, help="--serve / --call : port (défaut selon protocole)")
    opts.add_argument("--timeout", type=float, default=5.0, help="--call : timeout en secondes")
    opts.add_argument("--trace", action="store_true", help="--call custom / --serve : afficher la trace Sous le capot")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser.parse_args(argv)


class _RemoteEndpoints:
    """Adapte host/port fournis en ligne de commande à l'interface attendue par cli_runner.invoke()."""

    def __init__(self, host, protocol, port):
        from grpc_impl.grpc_client import InventoryGRPCClient
        from rest.rest_client import RestClient
        from rpc_core import RPCClient
        self._host, self._port = host, port or DEFAULT_PORTS[protocol]
        self._RPCClient, self._GRPC, self._Rest = RPCClient, InventoryGRPCClient, RestClient

    def custom_client(self, timeout=5.0, tracer=None, persistent=False):
        return self._RPCClient(host=self._host, port=self._port, timeout=timeout, tracer=tracer)

    def grpc_client(self, timeout=5.0, interceptors=None):
        c = self._GRPC(host=self._host, port=self._port, timeout=timeout, interceptors=interceptors)
        c.connect()
        return c

    def rest_client(self, timeout=5.0):
        return self._Rest(base_url=f"http://{self._host}:{self._port}", timeout=timeout)


def do_call(args) -> int:
    from cli.cli_runner import PROTOCOLS, invoke, parse_kv_args
    from under_the_hood import RPCTracer
    if len(args.call) < 2 or args.call[0] not in PROTOCOLS:
        print(f"Usage : --call {{{','.join(PROTOCOLS)}}} METHODE [nom=valeur ...]")
        return 2
    protocol, method, kv = args.call[0], args.call[1], parse_kv_args(args.call[2:])
    tracer = RPCTracer() if args.trace else None
    endpoints = _RemoteEndpoints(args.host, protocol, args.port)
    try:
        result = invoke(endpoints, protocol, method, kv, tracer=tracer, timeout=args.timeout)
    except Exception as exc:  # affichage pédagogique de l'erreur distante/réseau
        import grpc
        if isinstance(exc, grpc.RpcError):
            print(f"ÉCHEC de l'appel distant : grpc.RpcError {exc.code().name}: {exc.details()}")
        else:
            print(f"ÉCHEC de l'appel distant : {type(exc).__name__}: {exc}")
        return 1
    finally:
        if tracer:
            tracer.display_trace()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def run_full_demo(args) -> int:
    from cli.ui import title
    from contract_evolution.demo import run_contract_demo
    from lab.benchmark import run_benchmark
    from lab.failures import run_failure_demo
    from lab.streaming import run_streaming_demo
    from lab.transparency import run_transparency_demo
    from under_the_hood.explorer import run_under_the_hood_demo
    title("DÉMONSTRATION COMPLÈTE — 5 étapes")
    run_transparency_demo()                                  # 1-3 appel local / RPC / REST
    run_under_the_hood_demo("update_stock")                  # 4-6 sous le capot + Protobuf
    run_under_the_hood_demo("stream_analytics")              # 7  streaming
    run_streaming_demo()                                     # 7b réponse unique vs flux
    run_benchmark(iterations=min(args.iterations, 500), warmup=min(args.warmup, 50),
                  output_dir=None if args.no_save else "results")  # 8
    run_failure_demo()                                       # 9-11 latence, timeout, panne
    run_contract_demo()                                      # 12 contrat
    return 0


def main(argv=None) -> int:
    args = parse_arguments(argv)

    if args.dashboard:
        from dashboard.app import run_dashboard
        run_dashboard(host=args.host, port=args.port or 8080)
        return 0
    if args.serve:
        from lab.servers import serve_forever
        serve_forever(args.serve, args.host, args.port, trace=args.trace)
        return 0
    if args.call:
        return do_call(args)
    if args.demo:
        return run_full_demo(args)
    if args.benchmark:
        from lab.benchmark import run_benchmark
        run_benchmark(iterations=args.iterations, warmup=args.warmup,
                      output_dir=None if args.no_save else "results")
        return 0
    if args.simulate_failures:
        from lab.failures import run_failure_demo
        run_failure_demo()
        return 0
    if args.under_the_hood:
        from cli.cli_runner import parse_kv_args
        from under_the_hood.explorer import run_under_the_hood_demo
        run_under_the_hood_demo(args.method, parse_kv_args(args.args) if args.args else None)
        return 0
    if args.transparency_demo:
        from lab.transparency import run_transparency_demo
        run_transparency_demo()
        return 0
    if args.streaming_demo:
        from lab.streaming import run_streaming_demo
        run_streaming_demo()
        return 0
    if args.contract_demo:
        from contract_evolution.demo import run_contract_demo
        run_contract_demo()
        return 0

    from cli.cli_runner import CLIRunner
    CLIRunner().run_interactive_menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
