"""
Package Business Layer

Contient la logique métier pure, complètement indépendante des protocoles
de communication (Custom RPC, gRPC, REST).
"""

from .inventory_service import InventoryService

__all__ = ["InventoryService"]
