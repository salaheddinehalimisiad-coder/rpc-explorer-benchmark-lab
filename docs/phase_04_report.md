# RAPPORT DE PHASE 04 — gRPC & PROTOBUF

**Date :** 26 septembre 2026  
**Phase :** 04 — Implémentation gRPC / Protobuf  
**Statut :** PASS  
**Commit :** *(sera complété après validation et push)*

---

## 1. Objectifs & Périmètre de la Phase 04

L'objectif de la Phase 04 est d'implémenter l'approche RPC moderne basée sur un contrat IDL strict (Protobuf) et un transport binaire HTTP/2 haute performance (gRPC), en réutilisant exclusivement la logique métier `InventoryService` développée en Phase 03.

### Périmètre réalisé :
1. **Installation & Vérification des Dépendances :** `grpcio` (1.84.0), `grpcio-tools` (1.84.0), `protobuf` (7.36.2).
2. **Résolution du Shadowing de Module (`grpc/`) :** Conception d'un pont transparent dans `grpc/__init__.py` conciliant le package officiel Google `grpc` et les sous-modules du projet sans altération de l'arborescence.
3. **Compilation Protobuf IDL :** Compilation de `protos/inventory.proto` produisant `protos/inventory_pb2.py` et `protos/inventory_pb2_grpc.py`.
4. **Serveur gRPC (`grpc/grpc_server.py`) :**
   - Servicer `InventoryServicer` héritant de `inventory_pb2_grpc.InventoryRPCServiceServicer`.
   - Délégation totale vers `InventoryService` (aucune duplication métier).
   - Gestion de la contrainte `int64` du contrat Protobuf pour `CalculateFactorial` ($n \le 20$).
   - Codes de statut gRPC explicites (`INVALID_ARGUMENT`, `NOT_FOUND`, `FAILED_PRECONDITION`).
   - Vrai **Server Streaming** gRPC pour `StreamAnalytics` (émission unitaire continue via `yield`).
   - Gestionnaire de cycle de vie `InventoryGRPCServer` avec port dynamique (`port=0`) et arrêt gracieux.
5. **Client gRPC (`grpc/grpc_client.py`) :**
   - Encapsulation du stub `InventoryRPCServiceStub` et du canal HTTP/2.
   - Méthodes unaires typées (`calculate_factorial`, `get_product_details`, `update_stock`).
   - Méthode de flux continu (`stream_analytics`) consommant l'itérateur d'événements.
   - Fermeture propre (`close`) et context manager (`__enter__` / `__exit__`).
6. **Suite de Tests Dédiée (`tests/test_grpc.py`) :** 30 tests unitaires et d'intégration réels.

---

## 2. Décisions de Conception & Traitement des Contraintes

### D1 — Résolution de l'ombrage de nom (Module Shadowing)
- **Défi :** Le répertoire racine `grpc/` masquait le package officiel `grpc` de `site-packages` lors des exécutions depuis la racine du projet.
- **Solution mise en œuvre :** `grpc/__init__.py` localise dynamiquement le package officiel `grpc` hors de l'arborescence du projet, lie les sous-répertoires dans `__path__`, injecte le module système dans `sys.modules["grpc"]` et y expose conjointement les composants locaux (`InventoryGRPCServer`, `InventoryGRPCClient`).

### D2 — Contrainte de capacité Protobuf `int64` pour Factorielle
- **Constat :** Dans `protos/inventory.proto`, `FactorialResponse.result` est typé `int64` (signé, valeur max $9.22 \times 10^{18}$).
- **Comportement :** Pour $n \le 20$, $20! = 2\,432\,902\,008\,176\,640\,000$ est représentable. Pour $n > 20$, la valeur dépasse la capacité de `int64`. Le servicer gRPC intercepte les requêtes avec $n > 20$ et renvoie explicitement le code `grpc.StatusCode.INVALID_ARGUMENT` en indiquant le dépassement de contrat Protobuf.

### D3 — Codes de statut gRPC explicites
Les exceptions levées par la couche métier sont traduites vers des statuts gRPC formels :
- Produit inexistant dans le catalogue $\rightarrow$ `grpc.StatusCode.NOT_FOUND`
- Stock insuffisant pour un retrait $\rightarrow$ `grpc.StatusCode.FAILED_PRECONDITION`
- Arguments hors bornes ou invalides $\rightarrow$ `grpc.StatusCode.INVALID_ARGUMENT`
- Erreur imprévue $\rightarrow$ `grpc.StatusCode.INTERNAL`

### D4 — Distinction du streaming : Custom RPC vs gRPC
- **Phase 03 (Custom RPC) :** Protocole synchrone request/response retournant une liste JSON complète en un seul message.
- **Phase 04 (gRPC) :** Vrai streaming réseau HTTP/2 unidirectionnel serveur (`returns (stream AnalyticsResponse)`), émettant les événements individuellement au fil de l'eau.

---

## 3. Résultats Réels des Tests

Toute la suite de tests a été exécutée avec succès sans régression sur les phases précédentes.

```text
Ran 105 tests in 3.681s

OK
```

### Ventilation des 105 tests :
* **Tests de structure (`test_structure.py`) :** 4 tests (PASS)
* **Tests d'importation & interfaces (`test_imports.py`) :** 8 tests (PASS, actualisé pour gRPC)
* **Tests Custom RPC Core (`test_custom_rpc.py`) :** 13 tests (PASS)
* **Tests Service Métier (`test_business.py`) :** 50 tests (PASS)
* **Tests gRPC / Protobuf (`test_grpc.py`) :** 30 tests (PASS)
  - 5 tests de messages et compacité binaire Protobuf vs JSON
  - 12 tests unitaires du Servicer (cas nominaux, int64, codes NOT_FOUND, FAILED_PRECONDITION)
  - 13 tests d'intégration Client $\rightarrow$ Serveur de bout en bout (port dynamique, unaires, streaming, context managers)

---

## 4. Fichiers Modifiés et Créés

| Action | Fichier |
|--------|---------|
| **Modifié** | `grpc/__init__.py` (bridge vers package officiel) |
| **Modifié** | `grpc/grpc_server.py` (servicer + gestionnaire de serveur) |
| **Modifié** | `grpc/grpc_client.py` (client typé et streaming) |
| **Créé** | `protos/__init__.py` |
| **Créé** | `protos/inventory_pb2.py` (généré par protoc) |
| **Créé** | `protos/inventory_pb2_grpc.py` (généré par protoc) |
| **Créé** | `tests/test_grpc.py` (30 tests) |
| **Modifié** | `tests/test_imports.py` (actualisation des assertions) |
| **Modifié** | `.gitignore` (suivi des stubs générés pour exécution immédiate) |
| **Créé** | `docs/phase_04_report.md` |
| **Modifié** | `PROJECT_AUDIT.md` |

---

## 5. Bilan & État du Dépôt

- **Aucune régression** sur les Phases 01, 02 et 03.
- **Composants hors périmètre préservés :** `rest/`, `benchmark/`, `failure_simulator/`, `under_the_hood/`, `cli/` sont strictement intacts.
- **Couche métier isolée :** `business/inventory_service.py` n'a reçu aucune dépendance réseau ou gRPC.
