#!/usr/bin/env python3
"""
Point d'entrée principal : RPC Explorer & Benchmark Lab

Modes disponibles :
  python main.py --benchmark [--iterations N] [--warmup N] [--protocols local,custom,grpc,rest]
                 [--operation calculate_factorial] [--output rapport.json]
  python main.py --simulate-failures [--iterations N] [--output resultats.json]
  python main.py --simulate-latency 200 [--iterations N]
  python main.py --simulate-timeout 5 [--client-timeout 1.0]
  python main.py --interactive

Chaque mode démarre lui-même les serveurs Custom RPC, gRPC et REST
sur 127.0.0.1 (ports éphémères) puis les arrête à la fin.
"""

import sys
import argparse
from typing import List, Optional

from cli.cli_runner import CLIRunner, OPERATIONS, parse_protocols


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Configure et parse les arguments en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="RPC Explorer & Benchmark Lab — Démonstrateur pédagogique des Remote Procedure Calls"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--benchmark",
        action="store_true",
        help="Lancer le banc de test comparatif (latence, taille des payloads, sérialisation)"
    )
    modes.add_argument(
        "--simulate-failures",
        action="store_true",
        help="Lancer la démonstration de simulation de pannes (latence, timeout, crash, isolation)"
    )
    modes.add_argument(
        "--simulate-latency",
        type=float,
        metavar="MS",
        help="Comparer la baseline à une latence artificielle de MS millisecondes"
    )
    modes.add_argument(
        "--simulate-timeout",
        type=float,
        metavar="SECONDES",
        help="Retarder la réponse serveur de SECONDES pour déclencher le timeout client"
    )
    modes.add_argument(
        "--interactive",
        action="store_true",
        help="Ouvrir le menu interactif en console"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Nombre de requêtes mesurées par protocole (défaut : 1000 en benchmark, 30 en pannes)"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=50,
        help="Nombre d'appels de chauffe non mesurés (benchmark, défaut : 50)"
    )
    parser.add_argument(
        "--protocols",
        default=None,
        help="Protocoles à comparer, séparés par des virgules : local,custom,grpc,rest (défaut : tous)"
    )
    parser.add_argument(
        "--operation",
        default="calculate_factorial",
        choices=list(OPERATIONS),
        help="Opération métier à mesurer (benchmark, défaut : calculate_factorial)"
    )
    parser.add_argument(
        "--client-timeout",
        type=float,
        default=1.0,
        help="Timeout client en secondes pour --simulate-timeout (défaut : 1.0)"
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FICHIER.json",
        help="Écrire le rapport JSON dans ce fichier (benchmark, simulate-failures)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="RPC Explorer & Benchmark Lab v0.1.0"
    )
    args = parser.parse_args(argv)

    try:
        args.protocols = parse_protocols(args.protocols)
    except ValueError as err:
        parser.error(str(err))
    if args.iterations is not None and args.iterations < 1:
        parser.error("--iterations doit être >= 1")
    if args.warmup < 0:
        parser.error("--warmup doit être >= 0")
    if args.simulate_latency is not None and args.simulate_latency < 0:
        parser.error("--simulate-latency doit être >= 0")
    if args.simulate_timeout is not None and args.simulate_timeout <= 0:
        parser.error("--simulate-timeout doit être > 0")
    if args.client_timeout <= 0:
        parser.error("--client-timeout doit être > 0")
    return args


def main(argv: Optional[List[str]] = None, runner: Optional[CLIRunner] = None) -> int:
    """Point d'entrée de l'application."""
    args = parse_arguments(argv)
    runner = runner if runner is not None else CLIRunner()

    if args.benchmark:
        runner.run_benchmark_mode(
            iterations=args.iterations or 1000,
            warmup_iterations=args.warmup,
            protocols=args.protocols,
            operation=args.operation,
            output_path=args.output,
        )
        return 0

    if args.simulate_failures:
        runner.run_failure_demo(iterations=args.iterations or 30, output_path=args.output)
        return 0

    if args.simulate_latency is not None:
        runner.run_latency_demo(args.simulate_latency, iterations=args.iterations or 30)
        return 0

    if args.simulate_timeout is not None:
        runner.run_timeout_demo(args.simulate_timeout, client_timeout=args.client_timeout)
        return 0

    if args.interactive:
        runner.run_interactive_menu()
        return 0

    print("================================================================================")
    print(" RPC Explorer & Benchmark Lab — Laboratoire Pédagogique des RPC")
    print("================================================================================")
    print("Utilisez 'python main.py --help' pour consulter les modes disponibles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
