"""
Simulateur de Pannes Réseau et Contrats (Chaos Simulator)

Permet d'injecter des défaillances artificielles pour observer le comportement
des clients distants vs appels locaux :
- Injection de latence artificielle
- Simulation de coupure réseau / serveur indisponible
- Déclenchement de timeouts et retries
- Démonstration de breaking changes (incompatibilité de contrat)

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 09 et 10.
"""

from typing import Dict, Any, Optional


class FailureSimulator:
    """
    Gestionnaire d'injection d'anomalies réseau et protocolaires.
    """

    def __init__(self, latency_ms: float = 0.0, drop_rate: float = 0.0):
        self.latency_ms = latency_ms
        self.drop_rate = drop_rate
        self.is_active = False

    def enable_latency_spike(self, delay_ms: float = 200.0):
        """Active un délai artificiel pour tester les timeouts."""
        raise NotImplementedError("enable_latency_spike sera implémenté en Phase 09")

    def simulate_server_down(self):
        """Simule un serveur éteint ou inaccessible."""
        raise NotImplementedError("simulate_server_down sera implémenté en Phase 09")

    def simulate_contract_breaking_change(self):
        """Simule un changement non rétrocompatible de signature pour observer l'échec IDL."""
        raise NotImplementedError("simulate_contract_breaking_change sera implémenté en Phase 10")
