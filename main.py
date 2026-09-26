#!/usr/bin/env python3
"""
Point d'entrée principal : RPC Explorer & Benchmark Lab

Permet de piloter l'application selon les options définies dans le cahier des charges :
  python main.py --benchmark
  python main.py --simulate-failures
  python main.py --interactive (ou sans argument)

STATUT : SQUELETTE DE FONDATION (Phase 01)
"""

import sys
import argparse


def parse_arguments():
    """Configure et parse les arguments en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="RPC Explorer & Benchmark Lab — Démonstrateur pédagogique des Remote Procedure Calls"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Lancer le banc de test comparatif (Taille paquets, temps moyen par appel Local vs Custom vs gRPC)"
    )
    parser.add_argument(
        "--simulate-failures",
        action="store_true",
        help="Lancer la démonstration de simulation de pannes (latence, déconnexion, timeouts)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Ouvrir le menu interactif en console"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="RPC Explorer & Benchmark Lab v0.1.0 (Phase 01 - Foundation)"
    )
    return parser.parse_args()


def main():
    """Point d'entrée de l'application."""
    args = parse_arguments()

    if args.benchmark:
        print("[RPC Explorer] Mode Benchmark demandé.")
        print("[STATUT] Le moteur de benchmark sera opérationnel en Phase 08.")
        return 0

    if getattr(args, "simulate_failures", False):
        print("[RPC Explorer] Mode Simulation de Pannes demandé.")
        print("[STATUT] Le simulateur de pannes sera opérationnel en Phase 09.")
        return 0

    print("================================================================================")
    print(" RPC Explorer & Benchmark Lab — Laboratoire Pédagogique des RPC")
    print(" Phase 01 : Fondation & Architecture initialisée avec succès.")
    print("================================================================================")
    print("Utilisez 'python main.py --help' pour consulter les modes disponibles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
