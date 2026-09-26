"""
Service Métier : Calcul & Gestion d'Inventaire Distribué

Ce service contient la logique métier pure du projet.
Il ne dépend d'aucun protocole réseau ni framework RPC.

Méthodes prévues par le cahier des charges officiel :
- calculate_factorial : Calcul intensif de factorielle
- get_product_details : Consultation des détails d'un article en stock
- update_stock : Modification de la quantité en stock
- stream_analytics : Flux de métriques et télémétrie en streaming

STATUT: SQUELETTE / PLACEHOLDER — Implémentation prévue en Phase 03
"""

from typing import Dict, Any, Iterator, Optional


class InventoryService:
    """
    Logique métier de gestion de stock et de calcul.
    Complètement agnostique du mécanisme de transport ou de sérialisation.
    """

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        """
        Initialise le service métier.
        
        Args:
            initial_data: Données initiales facultatives pour initialiser le stock.
        """
        self._initial_data = initial_data or {}

    def calculate_factorial(self, n: int) -> int:
        """
        Calcule la factorielle d'un entier n (démonstrateur d'appel synchrone avec charge CPU).
        
        Args:
            n: Nombre entier positif ou nul.
            
        Returns:
            int: Résultat de n!
        """
        # Squelette de Phase 01 - implémentation en Phase 03
        raise NotImplementedError("calculate_factorial sera implémenté en Phase 03")

    def get_product_details(self, item_id: str) -> Dict[str, Any]:
        """
        Récupère les détails d'un produit par son identifiant.
        
        Args:
            item_id: Identifiant unique du produit.
            
        Returns:
            dict: Détails du produit (id, nom, catégorie, prix, stock, etc.).
        """
        # Squelette de Phase 01 - implémentation en Phase 03
        raise NotImplementedError("get_product_details sera implémenté en Phase 03")

    def update_stock(self, item_id: str, quantity_delta: int) -> Dict[str, Any]:
        """
        Met à jour la quantité en stock d'un produit.
        
        Args:
            item_id: Identifiant du produit.
            quantity_delta: Variation de quantité (positive ou négative).
            
        Returns:
            dict: État mis à jour du produit.
        """
        # Squelette de Phase 01 - implémentation en Phase 03
        raise NotImplementedError("update_stock sera implémenté en Phase 03")

    def stream_analytics(self, metric_name: str) -> Iterator[Dict[str, Any]]:
        """
        Génère un flux d'événements et d'analyses en temps réel (streaming).
        
        Args:
            metric_name: Nom de la métrique à observer.
            
        Yields:
            dict: Événement de télémétrie horodaté.
        """
        # Squelette de Phase 01 - implémentation en Phase 03
        raise NotImplementedError("stream_analytics sera implémenté en Phase 03")
        if False:  # Pour préserver le statut de générateur Python
            yield {}
