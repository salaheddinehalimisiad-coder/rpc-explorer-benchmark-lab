"""
Package Interface Utilisateur / CLI

Interface en ligne de commande interactive et démonstrateur du banc d'essai RPC.
Fournit CLIRunner (menu, benchmark, pannes) et LabServers (serveurs locaux du labo).
"""

from .cli_runner import CLIRunner, LabServers

__all__ = ["CLIRunner", "LabServers"]
