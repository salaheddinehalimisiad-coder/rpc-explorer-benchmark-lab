"""
Serveur REST HTTP / JSON

Expose les méthodes métier (InventoryService) via des endpoints HTTP REST
conçus selon les standards RESTful pour comparaison expérimentale avec RPC.
Conforme aux spécifications d'architecture et au cahier des charges officiel.
"""

import time
import threading
from typing import Optional, Dict, Any
from werkzeug.serving import make_server
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from business.inventory_service import InventoryService


def create_app(
    service: Optional[InventoryService] = None,
    failure_simulator: Optional[Any] = None,
) -> Flask:
    """
    Factory créant et configurant l'application Flask REST.
    Délègue l'exécution métier à l'instance InventoryService injectée.
    """
    app = Flask(__name__)
    CORS(app)

    # Injection du service métier
    svc = service if service is not None else InventoryService()
    app.config["INVENTORY_SERVICE"] = svc
    app.config["FAILURE_SIMULATOR"] = failure_simulator

    @app.before_request
    def check_failure_simulation():
        sim = app.config.get("FAILURE_SIMULATOR")
        if sim is not None:
            try:
                sim.apply_pre_execution_hooks()
            except ConnectionAbortedError as crash_err:
                return jsonify({
                    "error": f"Server crash: {crash_err}",
                    "code": "SERVER_UNAVAILABLE",
                    "status_code": 503,
                }), 503

    @app.route("/health", methods=["GET"])
    def health():
        """Vérification de l'état de santé du serveur REST."""
        return jsonify({
            "status": "ok",
            "service": "inventory_rest",
        }), 200

    @app.route("/api/factorial", methods=["POST"])
    def calculate_factorial():
        """
        Calcul de factorielle (appel CPU-bound via POST).
        Body JSON : {"n": int}
        """
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "n" not in data:
            return jsonify({
                "error": "Corps de requête invalide : champ 'n' requis.",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        n = data.get("n")
        # Validation stricte du type : exclusion des booléens
        if not isinstance(n, int) or isinstance(n, bool):
            return jsonify({
                "error": f"Le paramètre 'n' doit être un entier. Reçu : {type(n).__name__}",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        start_time = time.perf_counter()
        try:
            result = svc.calculate_factorial(n)
        except ValueError as exc:
            return jsonify({
                "error": str(exc),
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400
        except Exception as exc:
            return jsonify({
                "error": f"Erreur interne : {exc}",
                "code": "INTERNAL_SERVER_ERROR",
                "status_code": 500,
            }), 500

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return jsonify({
            "n": n,
            "result": result,
            "execution_time_ms": elapsed_ms,
        }), 200

    @app.route("/api/products/<item_id>", methods=["GET"])
    def get_product(item_id: str):
        """
        Consultation des détails d'un produit.
        Retourne 200 OK ou 404 Not Found.
        """
        if not item_id or not item_id.strip():
            return jsonify({
                "error": "L'identifiant produit 'item_id' ne peut pas être vide.",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        try:
            prod = svc.get_product_details(item_id)
            return jsonify(prod), 200
        except ValueError as exc:
            err_msg = str(exc)
            if "introuvable" in err_msg.lower() or "non trouvé" in err_msg.lower():
                return jsonify({
                    "error": err_msg,
                    "code": "NOT_FOUND",
                    "status_code": 404,
                }), 404
            return jsonify({
                "error": err_msg,
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400
        except Exception as exc:
            return jsonify({
                "error": f"Erreur interne : {exc}",
                "code": "INTERNAL_SERVER_ERROR",
                "status_code": 500,
            }), 500

    @app.route("/api/products/<item_id>/stock", methods=["POST"])
    def update_stock(item_id: str):
        """
        Mise à jour du stock d'un produit.
        Body JSON : {"quantity_delta": int} ou {"delta": int}
        Retourne 200 OK, 404 Not Found ou 409 Conflict si stock insuffisant.
        """
        if not item_id or not item_id.strip():
            return jsonify({
                "error": "L'identifiant produit 'item_id' ne peut pas être vide.",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({
                "error": "Corps de requête invalide : objet JSON attendu.",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        delta = data.get("quantity_delta", data.get("delta"))
        if not isinstance(delta, int) or isinstance(delta, bool):
            return jsonify({
                "error": "Le paramètre 'quantity_delta' doit être un entier.",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        try:
            res = svc.update_stock(item_id, delta)
            return jsonify(res), 200
        except ValueError as exc:
            err_msg = str(exc)
            if "introuvable" in err_msg.lower() or "non trouvé" in err_msg.lower():
                return jsonify({
                    "error": err_msg,
                    "code": "NOT_FOUND",
                    "status_code": 404,
                }), 404
            elif "insuffisant" in err_msg.lower():
                return jsonify({
                    "error": err_msg,
                    "code": "INSUFFICIENT_STOCK",
                    "status_code": 409,
                }), 409
            return jsonify({
                "error": err_msg,
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400
        except Exception as exc:
            return jsonify({
                "error": f"Erreur interne : {exc}",
                "code": "INTERNAL_SERVER_ERROR",
                "status_code": 500,
            }), 500

    @app.route("/api/analytics/<metric_name>", methods=["GET"])
    def get_analytics(metric_name: str):
        """
        Consultation d'événements de métrique (réponse JSON globale).
        Query param facultatif : ?count=10
        """
        count_str = request.args.get("count", "10")
        try:
            count = int(count_str)
        except ValueError:
            return jsonify({
                "error": f"Le paramètre 'count' doit être un entier valide. Reçu : {count_str!r}",
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400

        try:
            events = svc.stream_analytics(metric_name, count)
            return jsonify({
                "metric": metric_name,
                "count": len(events),
                "events": events,
            }), 200
        except ValueError as exc:
            return jsonify({
                "error": str(exc),
                "code": "INVALID_ARGUMENT",
                "status_code": 400,
            }), 400
        except Exception as exc:
            return jsonify({
                "error": f"Erreur interne : {exc}",
                "code": "INTERNAL_SERVER_ERROR",
                "status_code": 500,
            }), 500

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": "Ressource introuvable.",
            "code": "NOT_FOUND",
            "status_code": 404,
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({
            "error": "Méthode HTTP non autorisée pour cette ressource.",
            "code": "METHOD_NOT_ALLOWED",
            "status_code": 405,
        }), 405

    return app


class RestServer:
    """
    Gestionnaire du cycle de vie du serveur HTTP/REST encapsulant Flask.
    Supporte l'exécution en arrière-plan (thread) et les ports dynamiques.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5001,
        service: Optional[InventoryService] = None,
        failure_simulator: Optional[Any] = None,
    ):
        self.host = host
        self.port = port
        self.service = service if service is not None else InventoryService()
        self.failure_simulator = failure_simulator
        self.app = create_app(self.service, failure_simulator=self.failure_simulator)
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self.bound_port: int = port
        self.is_running: bool = False

    def start(self, threaded: bool = True) -> int:
        """
        Démarre le serveur REST.
        Si port=0, un port dynamique libre est alloué par le système.
        Retourne le port effectif d'écoute.
        """
        if self.is_running:
            return self.bound_port

        self._server = make_server(self.host, self.port, self.app, threaded=True)
        # Port réellement alloué par le socket
        self.bound_port = self._server.server_port
        self.is_running = True

        if threaded:
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="RestServerThread",
                daemon=True,
            )
            self._thread.start()
        else:
            self._server.serve_forever()

        return self.bound_port

    def stop(self):
        """Arrête proprement le serveur HTTP et libère la socket."""
        if self._server and self.is_running:
            self._server.shutdown()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3.0)
            self.is_running = False
            self._server = None
            self._thread = None

    def __enter__(self):
        self.start(threaded=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
