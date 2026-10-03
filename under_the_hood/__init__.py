"""
Package Under The Hood

Module de traçabilité pédagogique et d'inspection pas-à-pas du cycle RPC.
- tracer.py : frise des étapes du Custom RPC (client + serveur)
- protobuf_inspector.py : décodage du binaire Protobuf et intercepteur gRPC
- explorer.py : démonstration comparée Custom RPC / gRPC / REST
"""

from .tracer import RPCTracer

__all__ = ["RPCTracer"]
