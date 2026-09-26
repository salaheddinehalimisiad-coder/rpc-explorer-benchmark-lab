"""
RPC Core Package

Ce package contient l'implémentation du RPC Custom (from scratch).

Composants:
- serializer.py: Sérialisation/Désérialisation JSON des messages RPC
- client_stub.py: Client RPC avec transparence d'appel
- server_skeleton.py: Serveur RPC avec dispatcher et skeleton
"""

__version__ = "1.0.0"
__all__ = ["serializer", "client_stub", "server_skeleton"]
