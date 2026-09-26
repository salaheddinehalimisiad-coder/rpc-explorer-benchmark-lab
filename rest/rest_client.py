"""
Client REST HTTP / JSON

Consomme l'API REST via requêtes HTTP standard (GET/POST) avec typage
et signatures cohérentes avec les clients Custom RPC et gRPC.
Conforme au cahier des charges officiel et aux spécifications d'architecture.
"""

from typing import Dict, Any, List, Optional
import requests


class RestClientError(Exception):
    """Exception levée lors d'un échec de requête HTTP REST."""

    def __init__(self, message: str, status_code: int = 500, error_code: str = "ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

    def __str__(self):
        return f"[{self.status_code} {self.error_code}] {self.message}"


class RestClient:
    """
    Client HTTP/REST consommant les endpoints du serveur RestServer.
    Gère la session HTTP, les sérialisations JSON et la levée d'erreurs structurées.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:5001", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Décode la réponse JSON ou lève une exception RestClientError."""
        try:
            data = response.json()
        except Exception:
            data = {"error": response.text}

        if not response.ok:
            error_msg = data.get("error", f"Erreur HTTP {response.status_code}")
            error_code = data.get("code", "HTTP_ERROR")
            raise RestClientError(
                message=error_msg,
                status_code=response.status_code,
                error_code=error_code,
            )

        return data

    def calculate_factorial(self, n: int) -> int:
        """
        Appel POST /api/factorial.
        Retourne la valeur de la factorielle.
        """
        url = f"{self.base_url}/api/factorial"
        try:
            resp = self.session.post(url, json={"n": n}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RestClientError(f"Échec de connexion au serveur REST : {exc}", status_code=503, error_code="CONNECTION_ERROR")

        data = self._handle_response(resp)
        return int(data["result"])

    def calculate_factorial_with_metadata(self, n: int) -> Dict[str, Any]:
        """
        Appel POST /api/factorial retournant résultat et temps d'exécution serveur (ms).
        """
        url = f"{self.base_url}/api/factorial"
        try:
            resp = self.session.post(url, json={"n": n}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RestClientError(f"Échec de connexion au serveur REST : {exc}", status_code=503, error_code="CONNECTION_ERROR")

        return self._handle_response(resp)

    def get_product_details(self, item_id: str) -> Dict[str, Any]:
        """
        Appel GET /api/products/{item_id}.
        Retourne un dictionnaire contenant les attributs du produit.
        """
        url = f"{self.base_url}/api/products/{item_id}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RestClientError(f"Échec de connexion au serveur REST : {exc}", status_code=503, error_code="CONNECTION_ERROR")

        return self._handle_response(resp)

    def update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """
        Appel POST /api/products/{item_id}/stock.
        Retourne les détails de la mutation de stock.
        """
        url = f"{self.base_url}/api/products/{item_id}/stock"
        try:
            resp = self.session.post(
                url, json={"quantity_delta": quantity_delta}, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise RestClientError(f"Échec de connexion au serveur REST : {exc}", status_code=503, error_code="CONNECTION_ERROR")

        return self._handle_response(resp)

    def stream_analytics(self, metric_name: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        Appel GET /api/analytics/{metric_name}?count={count}.
        Retourne la liste d'événements de métrique.
        """
        url = f"{self.base_url}/api/analytics/{metric_name}"
        try:
            resp = self.session.get(url, params={"count": count}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RestClientError(f"Échec de connexion au serveur REST : {exc}", status_code=503, error_code="CONNECTION_ERROR")

        data = self._handle_response(resp)
        return data.get("events", [])

    def health(self) -> Dict[str, Any]:
        """Appel GET /health pour vérifier la disponibilité de l'API."""
        url = f"{self.base_url}/health"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RestClientError(f"Échec de connexion au serveur REST : {exc}", status_code=503, error_code="CONNECTION_ERROR")

        return self._handle_response(resp)

    def close(self):
        """Ferme la session HTTP."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
