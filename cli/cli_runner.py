"""
Lanceur de l'interface en ligne de commande (CLI Runner)

Fournit un menu interactif et la gestion des arguments pour piloter :
- Les appels RPC unitaires et interactifs
- L'activation du mode "Sous le capot"
- Le lancement du banc d'essai comparatif
- La simulation de pannes réseau et ruptures de contrat

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 11.
"""

from typing import Optional, List


class CLIRunner:
    """
    Gestionnaire d'interface console et interactive.
    """

    def __init__(self):
        pass

    def run_interactive_menu(self):
        """Lance le menu interactif textuel."""
        raise NotImplementedError("run_interactive_menu sera implémenté en Phase 11")

    def run_benchmark_mode(self, iterations: int = 1000):
        """Lance la démonstration du banc de test comparatif."""
        raise NotImplementedError("run_benchmark_mode sera implémenté en Phase 11")

    def run_failure_demo(self):
        """Lance la démonstration interactive des pannes RPC."""
        raise NotImplementedError("run_failure_demo sera implémenté en Phase 11")
