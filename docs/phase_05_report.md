# RAPPORT DE PHASE 05 — REST API (HTTP / JSON)

**Date :** 26 septembre 2026  
**Phase :** 05 — Implémentation REST (HTTP/JSON)  
**Statut :** PASS  
**Commit :** `9b4402b` (vérifié sur origin/main)

---

## 1. Objectifs & Périmètre de la Phase 05

L'objectif de la Phase 05 est d'implémenter l'approche REST (HTTP/JSON) en réutilisant sans duplication la logique métier `InventoryService` (Phase 03). Cette implémentation fournit le troisième pilier architectural du laboratoire pédagogique, permettant la comparaison expérimentale (Phase 06) avec Custom RPC (Phase 02) et gRPC (Phase 04).

### Périmètre réalisé :
1. **Installation des Dépendances REST :** `flask` (3.1.3), `flask-cors` (6.0.5).
2. **Serveur REST (`rest/rest_server.py`) :**
   - Factory Flask `create_app(service)` avec support CORS.
   - Délégation complète vers `InventoryService` (aucune duplication métier).
   - Gestionnaire `RestServer` basé sur `werkzeug.serving.make_server` avec allocation de port dynamique (`port=0`), thread d'arrière-plan et arrêt gracieux (`shutdown`).
3. **Endpoints REST Implémentés :**
   - `POST /api/factorial` : Calcul de factorielle CPU-bound (`200 OK`, `400 Bad Request`).
   - `GET /api/products/<item_id>` : Consultation détails produit (`200 OK`, `404 Not Found`).
   - `POST /api/products/<item_id>/stock` : Mutation de stock (`200 OK`, `404 Not Found`, `409 Conflict` si stock insuffisant).
   - `GET /api/analytics/<metric_name>` : Consultation de flux métriques (`200 OK`, `400 Bad Request`).
   - `GET /health` : Endpoint de santé et disponibilité du service (`200 OK`).
4. **Client REST (`rest/rest_client.py`) :**
   - `RestClient` basé sur `requests.Session` pour la réutilisation des connexions HTTP.
   - Méthodes Python alignées avec les stubs Custom RPC et gRPC (`calculate_factorial`, `get_product_details`, `update_stock`, `stream_analytics`, `health`).
   - Exception dédiée `RestClientError` contenant `status_code` et `error_code`.
   - Support des context managers (`with RestClient(...) as client:`).
5. **Suite de Tests Dédiée (`tests/test_rest.py`) :** 28 tests (17 unitaires Flask test_client + 11 intégration réseau réelle et concurrence).
6. **Actualisation de `tests/test_imports.py` :** Remplacement des `NotImplementedError` obsolètes par des tests d'interface réels.

---

## 2. Décisions Techniques et Traitement des Contraintes

### D1 — Endpoints et Codes HTTP
- `200 OK` : Succès pour les opérations de lecture et mutation.
- `400 Bad Request` : Erreur de validation de schéma, type invalide ou argument hors bornes (`INVALID_ARGUMENT`).
- `404 Not Found` : Produit inexistant dans le catalogue de démonstration (`NOT_FOUND`).
- `409 Conflict` : Conflit d'état métier (stock insuffisant pour honorer le retrait, `INSUFFICIENT_STOCK`).
- `405 Method Not Allowed` : Méthode HTTP non autorisée sur la ressource.

### D2 — Cycle de vie du serveur HTTP
`RestServer` utilise `werkzeug.serving.make_server(host, port, app, threaded=True)`. Lorsqu'un port `0` est passé, le port éphémère est immédiatement disponible via `self.bound_port`. L'arrêt propre via `stop()` appelle `shutdown()` et attend la terminaison du thread daemon, évitant toute fuite de descripteur de socket sous Windows.

### D3 — Streaming REST
Conformément au cahier des charges et au plan validé, `stream_analytics` sous REST retourne la liste complète des événements dans un objet JSON (`{"metric": ..., "count": ..., "events": [...]}`). Le véritable streaming au fil de l'eau (frame par frame) est spécifique à gRPC (HTTP/2), ce qui met en valeur la différence pédagogique entre ces deux approches.

---

## 3. Résultats Réels des Tests

Exécution complète de la suite de tests du projet :

```text
Ran 133 tests in 5.623s

OK
```

### Ventilation des 133 tests :
* **Tests de structure (`test_structure.py`) :** 4 tests (PASS)
* **Tests d'importation & interfaces (`test_imports.py`) :** 8 tests (PASS)
* **Tests Custom RPC Core (`test_custom_rpc.py`) :** 13 tests (PASS)
* **Tests Service Métier (`test_business.py`) :** 50 tests (PASS)
* **Tests gRPC / Protobuf (`test_grpc.py`) :** 30 tests (PASS)
* **Tests REST HTTP/JSON (`test_rest.py`) :** 28 tests (PASS, NOUVEAU)
  - 17 tests unitaires de routes Flask (cas nominaux, bornes, 400, 404, 409, 405)
  - 11 tests d'intégration réseau Client $\rightarrow$ Serveur (port dynamique, factorielle, inventaire, stock, analytics, concurrence 10 threads, context managers)

---

## 4. Fichiers Modifiés et Créés

| Action | Fichier |
|--------|---------|
| **Modifié** | `rest/__init__.py` |
| **Modifié** | `rest/rest_server.py` |
| **Modifié** | `rest/rest_client.py` |
| **Créé** | `tests/test_rest.py` |
| **Modifié** | `tests/test_imports.py` |
| **Créé** | `docs/phase_05_report.md` |
| **Modifié** | `PROJECT_AUDIT.md` |

---

## 5. Bilan & État du Dépôt

- **Zéro régression :** Les 105 tests préexistants continuent de passer avec succès.
- **Périmètre préservé :** `business/`, `rpc_core/`, `grpc/`, `protos/`, `benchmark/`, `failure_simulator/`, `under_the_hood/`, `cli/` sont strictement intacts.
