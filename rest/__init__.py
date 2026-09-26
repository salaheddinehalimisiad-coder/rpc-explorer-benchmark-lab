"""
Package REST Implementation

Contient les composants de l'API HTTP/REST (Flask) pour les besoins comparatifs du laboratoire.
Expose le serveur REST, le client REST et les exceptions associées.
"""

from .rest_server import RestServer, create_app
from .rest_client import RestClient, RestClientError

__all__ = ["RestServer", "RestClient", "RestClientError", "create_app"]
