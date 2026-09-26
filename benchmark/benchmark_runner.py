"""
Moteur de Benchmark Comparatif

Mesure et compare :
- Latence (moyenne, médiane, p50, p95, p99)
- Throughput (requêtes / seconde)
- Taille des payloads sur le réseau (Octets sérialisés Protobuf vs JSON vs REST)
- Taux d'erreur

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 07 et 08.
"""

from typing import Dict, List, Any, Optional
from .adapters.base_adapter import BaseBenchmarkAdapter


class BenchmarkRunner:
    """
    Orchestrateur des campagnes de benchmark comparatives.
    """

    def __init__(self, adapters: Optional[List[BaseBenchmarkAdapter]] = None):
        self.adapters = adapters or []

    def run_latency_benchmark(self, adapter: BaseBenchmarkAdapter,
                             iterations: int = 1000) -> Dict[str, Any]:
        """
        Mesure la latence d'appels répétés pour un adaptateur donné.
        """
        raise NotImplementedError("run_latency_benchmark sera implémenté en Phase 07")

    def run_payload_size_comparison(self) -> Dict[str, Any]:
        """
        Mesure et compare la taille binaire des messages Protobuf vs JSON.
        """
        raise NotImplementedError("run_payload_size_comparison sera implémenté en Phase 08")

    def run_full_suite(self, iterations: int = 1000) -> Dict[str, Any]:
        """
        Lance l'ensemble de la suite de benchmark comparatif.
        """
        raise NotImplementedError("run_full_suite sera implémenté en Phase 08")
