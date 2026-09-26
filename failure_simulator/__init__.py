"""
Package Failure Simulator (Phase 07).

Simulateur de pannes et de defaillances reseau pour demontrer les limites
de la transparence RPC et observer les comportements des differents transports.
"""

from .simulator import FailureSimulator
from .latency_injector import LatencyInjector
from .network_fault import NetworkFaultSimulator
from .message_corruptor import MessageCorruptor
from .config import (
    FailureConfig,
    PRESET_NOMINAL,
    PRESET_LATENCY_50MS,
    PRESET_LATENCY_200MS,
    PRESET_TIMEOUT_3S,
    PRESET_SERVER_CRASH,
)

__all__ = [
    "FailureSimulator",
    "LatencyInjector",
    "NetworkFaultSimulator",
    "MessageCorruptor",
    "FailureConfig",
    "PRESET_NOMINAL",
    "PRESET_LATENCY_50MS",
    "PRESET_LATENCY_200MS",
    "PRESET_TIMEOUT_3S",
    "PRESET_SERVER_CRASH",
]
