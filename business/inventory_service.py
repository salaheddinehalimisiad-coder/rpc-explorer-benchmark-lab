"""
Service Métier : Calcul & Gestion d'Inventaire Distribué

Ce service contient la logique métier pure du projet.
Il ne dépend d'aucun protocole réseau ni framework RPC.

Méthodes implémentées :
- calculate_factorial : Calcul intensif de factorielle (itératif)
- get_product_details : Consultation des détails d'un article en stock
- update_stock : Modification de la quantité en stock (thread-safe)
- stream_analytics : Simulation de flux de métriques (réponse JSON unique)

STATUT: IMPLÉMENTÉ — Phase 03
"""

import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Catalogue de démonstration
# ─────────────────────────────────────────────────────────────────────────────
# DONNÉES DE DÉMONSTRATION UNIQUEMENT.
# Ce catalogue n'est PAS connecté à un véritable système d'inventaire.
# Il sert exclusivement à illustrer les appels RPC.
# ─────────────────────────────────────────────────────────────────────────────

DEMO_CATALOG = {
    "PROD-001": {
        "item_id": "PROD-001",
        "name": "Laptop ProBook 450",
        "category": "Electronics",
        "price": 1299.99,
        "stock": 42,
        "unit": "unit",
    },
    "PROD-002": {
        "item_id": "PROD-002",
        "name": "Clavier Mécanique RGB",
        "category": "Peripherals",
        "price": 89.90,
        "stock": 150,
        "unit": "unit",
    },
    "PROD-003": {
        "item_id": "PROD-003",
        "name": "Câble Ethernet Cat6 (3m)",
        "category": "Networking",
        "price": 12.50,
        "stock": 500,
        "unit": "unit",
    },
    "PROD-004": {
        "item_id": "PROD-004",
        "name": "SSD NVMe 1To",
        "category": "Storage",
        "price": 109.99,
        "stock": 75,
        "unit": "unit",
    },
    "PROD-005": {
        "item_id": "PROD-005",
        "name": "Écran 27\" 4K IPS",
        "category": "Displays",
        "price": 449.00,
        "stock": 20,
        "unit": "unit",
    },
    "PROD-006": {
        "item_id": "PROD-006",
        "name": "Module RAM DDR5 16Go",
        "category": "Memory",
        "price": 64.90,
        "stock": 200,
        "unit": "unit",
    },
}


# Métriques supportées par stream_analytics et leurs unités.
SUPPORTED_METRICS = {
    "cpu_usage": {"unit": "%", "min_val": 5.0, "max_val": 95.0},
    "memory_usage": {"unit": "%", "min_val": 20.0, "max_val": 90.0},
    "request_rate": {"unit": "req/s", "min_val": 10.0, "max_val": 500.0},
    "error_rate": {"unit": "%", "min_val": 0.0, "max_val": 15.0},
}


class InventoryService:
    """
    Logique métier de gestion de stock et de calcul.
    Complètement agnostique du mécanisme de transport ou de sérialisation.

    Thread-safety:
        Les opérations de modification du stock (update_stock) sont protégées
        par un threading.Lock afin de garantir la cohérence en environnement
        multi-threadé (serveur RPC concurrent).
    """

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        """
        Initialise le service métier.

        Args:
            initial_data: Données initiales facultatives pour initialiser le stock.
                          Si None, le catalogue de démonstration par défaut est utilisé.
        """
        if initial_data is not None:
            self._catalog: Dict[str, Dict[str, Any]] = {
                k: dict(v) for k, v in initial_data.items()
            }
        else:
            # Copie profonde du catalogue de démonstration pour isolation
            self._catalog = {
                k: dict(v) for k, v in DEMO_CATALOG.items()
            }

        self._lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. calculate_factorial
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_factorial(self, n: int) -> int:
        """
        Calcule la factorielle d'un entier n (démonstrateur d'appel synchrone avec charge CPU).

        Algorithme itératif pour éviter RecursionError sur les grandes valeurs.

        Args:
            n: Nombre entier positif ou nul.

        Returns:
            int: Résultat de n!

        Raises:
            ValueError: Si n n'est pas un entier, ou si n < 0, ou si n > 200.
        """
        # Validation stricte du type
        if not isinstance(n, int) or isinstance(n, bool):
            raise ValueError(
                f"Le paramètre 'n' doit être un entier. Reçu : {type(n).__name__} ({n!r})"
            )

        if n < 0:
            raise ValueError(
                f"Le paramètre 'n' doit être positif ou nul. Reçu : {n}"
            )

        if n > 200:
            raise ValueError(
                f"Le paramètre 'n' ne doit pas dépasser 200 (protection contre calcul excessif). Reçu : {n}"
            )

        # Algorithme itératif
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # 2. get_product_details
    # ─────────────────────────────────────────────────────────────────────────

    def get_product_details(self, item_id: str) -> Dict[str, Any]:
        """
        Récupère les détails d'un produit par son identifiant.

        Args:
            item_id: Identifiant unique du produit (ex: "PROD-001").

        Returns:
            dict: Détails du produit contenant :
                  item_id, name, category, price, stock, unit, last_updated.

        Raises:
            ValueError: Si item_id n'est pas une chaîne non vide.
            ValueError: Si le produit n'existe pas dans le catalogue.
        """
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError(
                f"Le paramètre 'item_id' doit être une chaîne non vide. Reçu : {item_id!r}"
            )

        with self._lock:
            if item_id not in self._catalog:
                raise ValueError(
                    f"Produit '{item_id}' introuvable dans le catalogue. "
                    f"Produits disponibles : {list(self._catalog.keys())}"
                )
            # Copie pour isoler l'état interne
            product = dict(self._catalog[item_id])

        product["last_updated"] = datetime.now(timezone.utc).isoformat()
        return product

    # ─────────────────────────────────────────────────────────────────────────
    # 3. update_stock
    # ─────────────────────────────────────────────────────────────────────────

    def update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """
        Met à jour la quantité en stock d'un produit.

        Opération thread-safe protégée par un verrou (Lock).

        Args:
            item_id: Identifiant du produit.
            quantity_delta: Variation de quantité (positive pour ajout, négative pour retrait).

        Returns:
            dict: État mis à jour contenant :
                  item_id, previous_stock, delta, new_stock, timestamp.

        Raises:
            ValueError: Si item_id n'est pas une chaîne non vide.
            ValueError: Si quantity_delta n'est pas un entier.
            ValueError: Si le produit n'existe pas dans le catalogue.
            ValueError: Si le stock résultant serait négatif.
        """
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError(
                f"Le paramètre 'item_id' doit être une chaîne non vide. Reçu : {item_id!r}"
            )

        if not isinstance(quantity_delta, int) or isinstance(quantity_delta, bool):
            raise ValueError(
                f"Le paramètre 'quantity_delta' doit être un entier. "
                f"Reçu : {type(quantity_delta).__name__} ({quantity_delta!r})"
            )

        with self._lock:
            if item_id not in self._catalog:
                raise ValueError(
                    f"Produit '{item_id}' introuvable dans le catalogue. "
                    f"Produits disponibles : {list(self._catalog.keys())}"
                )

            previous_stock = self._catalog[item_id]["stock"]
            new_stock = previous_stock + quantity_delta

            if new_stock < 0:
                raise ValueError(
                    f"Stock insuffisant pour '{item_id}'. "
                    f"Stock actuel : {previous_stock}, delta demandé : {quantity_delta}, "
                    f"stock résultant : {new_stock} (interdit < 0)."
                )

            self._catalog[item_id]["stock"] = new_stock

        return {
            "item_id": item_id,
            "previous_stock": previous_stock,
            "delta": quantity_delta,
            "new_stock": new_stock,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. stream_analytics
    # ─────────────────────────────────────────────────────────────────────────

    def stream_analytics(self, metric_name: str, num_events: int = 10) -> List[Dict[str, Any]]:
        """
        Simule la production d'un flux de métriques au niveau métier.

        IMPORTANT : Cette méthode ne constitue pas encore un streaming réseau
        RPC natif. Le protocole Custom RPC actuel est synchrone request/response.
        La réponse est donc une liste complète d'événements retournée en une
        seule réponse JSON. Le vrai streaming réseau pourra être étudié
        ultérieurement dans la partie gRPC si le cahier des charges le prévoit.

        Args:
            metric_name: Nom de la métrique à observer.
                         Valeurs supportées : cpu_usage, memory_usage,
                         request_rate, error_rate.
            num_events: Nombre d'événements à générer (par défaut 10, max 100).

        Returns:
            list[dict]: Liste d'événements de télémétrie, chacun contenant :
                        metric, value, unit, timestamp, sequence.

        Raises:
            ValueError: Si metric_name n'est pas une chaîne non vide.
            ValueError: Si metric_name n'est pas une métrique supportée.
            ValueError: Si num_events n'est pas un entier positif ou dépasse 100.
        """
        if not isinstance(metric_name, str) or not metric_name.strip():
            raise ValueError(
                f"Le paramètre 'metric_name' doit être une chaîne non vide. Reçu : {metric_name!r}"
            )

        if metric_name not in SUPPORTED_METRICS:
            raise ValueError(
                f"Métrique '{metric_name}' non supportée. "
                f"Métriques disponibles : {list(SUPPORTED_METRICS.keys())}"
            )

        if not isinstance(num_events, int) or isinstance(num_events, bool):
            raise ValueError(
                f"Le paramètre 'num_events' doit être un entier. "
                f"Reçu : {type(num_events).__name__} ({num_events!r})"
            )

        if num_events < 1 or num_events > 100:
            raise ValueError(
                f"Le paramètre 'num_events' doit être compris entre 1 et 100. Reçu : {num_events}"
            )

        metric_spec = SUPPORTED_METRICS[metric_name]
        events = list(self._generate_events(metric_name, metric_spec, num_events))
        return events

    @staticmethod
    def _generate_events(
        metric_name: str,
        metric_spec: Dict[str, Any],
        num_events: int,
    ):
        """
        Générateur interne d'événements de télémétrie.

        Produit des valeurs simulées déterministes basées sur la position
        dans la séquence pour garantir la reproductibilité des tests.
        """
        min_val = metric_spec["min_val"]
        max_val = metric_spec["max_val"]
        unit = metric_spec["unit"]
        value_range = max_val - min_val

        for seq in range(1, num_events + 1):
            # Valeur simulée déterministe : oscillation linéaire dans l'intervalle
            fraction = (seq - 1) / max(num_events - 1, 1)
            value = round(min_val + fraction * value_range, 2)

            yield {
                "metric": metric_name,
                "value": value,
                "unit": unit,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sequence": seq,
            }
