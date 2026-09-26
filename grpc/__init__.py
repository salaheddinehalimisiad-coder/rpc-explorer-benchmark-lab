"""
Package gRPC Implementation & Bridge

Permet la coexistence transparente entre :
1. La bibliothèque officielle Google `grpc` (issue de site-packages)
2. Les composants du projet (`grpc_server`, `grpc_client`, stubs générés)

Cette architecture résout le problème de shadowing sans altérer l'arborescence officielle.
"""

import sys
import os
import importlib.util
import importlib.machinery

_project_grpc_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_project_grpc_dir)

# Recherche du package officiel `grpc` dans site-packages
_search_paths = [
    p for p in sys.path
    if p and not os.path.abspath(p).startswith(_parent_dir)
]
_real_spec = importlib.machinery.PathFinder.find_spec("grpc", _search_paths)

if _real_spec and _real_spec.origin and os.path.abspath(_real_spec.origin) != os.path.abspath(__file__):
    _real_mod = importlib.util.module_from_spec(_real_spec)
    if _project_grpc_dir not in _real_mod.__path__:
        _real_mod.__path__.append(_project_grpc_dir)
    sys.modules["grpc"] = _real_mod
    _real_spec.loader.exec_module(_real_mod)

    # Exposer les composants locaux sur le module unifié
    try:
        from grpc.grpc_server import InventoryGRPCServer
        from grpc.grpc_client import InventoryGRPCClient
        _real_mod.InventoryGRPCServer = InventoryGRPCServer
        _real_mod.InventoryGRPCClient = InventoryGRPCClient
    except Exception:
        pass

__all__ = ["grpc_server", "grpc_client"]
