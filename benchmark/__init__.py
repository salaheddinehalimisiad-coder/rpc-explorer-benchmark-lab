"""
Package Benchmark Engine

Moteur de benchmarking comparatif des mécanismes RPC (Custom RPC vs gRPC vs REST vs Local).
Fournit l'orchestrateur BenchmarkRunner, le conteneur BenchmarkResult et les adaptateurs protocolaires.
"""

from .benchmark_runner import BenchmarkRunner
from .metrics import BenchmarkResult
from .adapters import (
    BaseBenchmarkAdapter,
    LocalAdapter,
    CustomRPCAdapter,
    GRPCAdapter,
    RESTAdapter,
)

__all__ = [
    "BenchmarkRunner",
    "BenchmarkResult",
    "BaseBenchmarkAdapter",
    "LocalAdapter",
    "CustomRPCAdapter",
    "GRPCAdapter",
    "RESTAdapter",
]
