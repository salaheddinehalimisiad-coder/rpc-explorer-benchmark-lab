"""
Package Adapters pour le banc d'essai

Fournit des adaptateurs uniformes pour tester Local, Custom RPC, gRPC et REST.
"""

from .base_adapter import BaseBenchmarkAdapter

__all__ = ["BaseBenchmarkAdapter"]
