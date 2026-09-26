"""
Conteneur de métriques et calculs statistiques pour le Benchmark Engine.

Calcule de manière fiable et déterministe les percentiles, la latence moyenne,
l'écart-type et le débit (RPS) en utilisant la bibliothèque standard Python (statistics, math).
"""

import math
import statistics
from typing import List, Dict, Any, Optional


class BenchmarkResult:
    """
    Encapsule les mesures brutes d'une campagne de benchmark et calcule
    les indicateurs statistiques de performance.
    """

    def __init__(
        self,
        name: str,
        operation: str,
        latencies_ms: List[float],
        total_time_seconds: float,
        warmup_iterations: int = 0,
        error_count: int = 0,
        concurrency: int = 1,
    ):
        self.name = name
        self.operation = operation
        self.latencies_ms = list(latencies_ms)
        self.total_time_seconds = float(total_time_seconds)
        self.warmup_iterations = int(warmup_iterations)
        self.error_count = int(error_count)
        self.concurrency = int(concurrency)
        self.iterations = len(self.latencies_ms) + self.error_count

        self._sorted_latencies = sorted(self.latencies_ms)

    @property
    def min_ms(self) -> float:
        """Latence minimale en millisecondes."""
        return self._sorted_latencies[0] if self._sorted_latencies else 0.0

    @property
    def max_ms(self) -> float:
        """Latence maximale en millisecondes."""
        return self._sorted_latencies[-1] if self._sorted_latencies else 0.0

    @property
    def mean_ms(self) -> float:
        """Latence moyenne en millisecondes."""
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def median_ms(self) -> float:
        """Latence médiane en millisecondes."""
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def std_dev_ms(self) -> float:
        """Écart-type de la latence en millisecondes."""
        if len(self.latencies_ms) >= 2:
            return statistics.stdev(self.latencies_ms)
        return 0.0

    def percentile(self, p: float) -> float:
        """
        Calcule le percentile p (ex: 50, 90, 95, 99) par interpolation linéaire standard.
        """
        if not self._sorted_latencies:
            return 0.0
        if len(self._sorted_latencies) == 1:
            return self._sorted_latencies[0]

        k = (len(self._sorted_latencies) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return self._sorted_latencies[int(k)]
        d0 = self._sorted_latencies[int(f)] * (c - k)
        d1 = self._sorted_latencies[int(c)] * (k - f)
        return d0 + d1

    @property
    def p50_ms(self) -> float:
        """Percentile 50 (médiane) en millisecondes."""
        return self.percentile(50.0)

    @property
    def p90_ms(self) -> float:
        """Percentile 90 en millisecondes."""
        return self.percentile(90.0)

    @property
    def p95_ms(self) -> float:
        """Percentile 95 en millisecondes."""
        return self.percentile(95.0)

    @property
    def p99_ms(self) -> float:
        """Percentile 99 en millisecondes."""
        return self.percentile(99.0)

    @property
    def throughput_rps(self) -> float:
        """Débit en requêtes par seconde (RPS)."""
        success_count = len(self.latencies_ms)
        if self.total_time_seconds > 0.0:
            return success_count / self.total_time_seconds
        return 0.0

    @property
    def error_rate(self) -> float:
        """Taux d'erreur en pourcentage (0.0 à 100.0)."""
        if self.iterations > 0:
            return (self.error_count / self.iterations) * 100.0
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Exporte l'ensemble des métriques sous forme de dictionnaire sérialisable."""
        return {
            "name": self.name,
            "operation": self.operation,
            "iterations": self.iterations,
            "success_count": len(self.latencies_ms),
            "error_count": self.error_count,
            "error_rate_percent": round(self.error_rate, 2),
            "concurrency": self.concurrency,
            "warmup_iterations": self.warmup_iterations,
            "total_time_seconds": round(self.total_time_seconds, 4),
            "throughput_rps": round(self.throughput_rps, 2),
            "latency_ms": {
                "min": round(self.min_ms, 4),
                "mean": round(self.mean_ms, 4),
                "median": round(self.median_ms, 4),
                "max": round(self.max_ms, 4),
                "std_dev": round(self.std_dev_ms, 4),
                "p50": round(self.p50_ms, 4),
                "p90": round(self.p90_ms, 4),
                "p95": round(self.p95_ms, 4),
                "p99": round(self.p99_ms, 4),
            },
        }

    def summary_str(self) -> str:
        """Formate une ligne de synthèse textuelle."""
        return (
            f"[{self.name}] {self.operation} (n={len(self.latencies_ms)}) | "
            f"mean: {self.mean_ms:.3f}ms | p50: {self.p50_ms:.3f}ms | "
            f"p95: {self.p95_ms:.3f}ms | p99: {self.p99_ms:.3f}ms | "
            f"rps: {self.throughput_rps:.1f}"
        )
