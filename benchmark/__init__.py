"""
Package Benchmark Engine

Moteur de benchmarking comparatif des mécanismes RPC (Custom RPC vs gRPC vs REST vs Local).
STATUT: SQUELETTE — Implémentation prévue en Phase 07 et 08.
"""

from .benchmark_runner import BenchmarkRunner

__all__ = ["BenchmarkRunner"]
