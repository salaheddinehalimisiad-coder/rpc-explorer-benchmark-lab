"""
Package benchmark.adapters

Contient l'interface commune BaseBenchmarkAdapter et les 4 adaptateurs :
- LocalAdapter (mémoire)
- CustomRPCAdapter (TCP + JSON)
- GRPCAdapter (HTTP/2 + Protobuf)
- RESTAdapter (HTTP/1.1 + JSON)
"""

from .base_adapter import BaseBenchmarkAdapter
from .local_adapter import LocalAdapter
from .custom_rpc_adapter import CustomRPCAdapter
from .grpc_adapter import GRPCAdapter
from .rest_adapter import RESTAdapter

__all__ = [
    "BaseBenchmarkAdapter",
    "LocalAdapter",
    "CustomRPCAdapter",
    "GRPCAdapter",
    "RESTAdapter",
]
