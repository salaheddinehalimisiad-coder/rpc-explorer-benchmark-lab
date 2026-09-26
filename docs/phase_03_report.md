# RAPPORT DE PHASE 03 — SERVICE MÉTIER (InventoryService)

**Date :** 26 septembre 2026  
**Phase :** 03 — Service Métier  
**Statut :** PASS  
**Commit :** *(sera complété après push)*

---

## 1. Objectif

Implémenter la logique métier du projet dans `business/inventory_service.py`, en la connectant au Custom RPC Core (Phase 02) tout en préservant l'indépendance du service vis-à-vis du transport.

---

## 2. Périmètre implémenté

### 2.1 `calculate_factorial(n: int) → int`

- **Algorithme :** Itératif (boucle `for`) — pas de récursion.
- **Validations :** type int (bool exclu), `n >= 0`, `n <= 200`.
- **Rôle pédagogique :** Appel RPC synchrone avec charge CPU.

### 2.2 `get_product_details(item_id: str) → Dict`

- **Source de données :** Catalogue de démonstration en mémoire (6 produits).
- **Validations :** type str non vide, existence dans le catalogue.
- **Erreur :** `ValueError` si produit inconnu (propagée en `EXECUTION_ERROR` via RPC).
- **Isolation :** Le résultat retourné est une copie — la modification du dict retourné n'affecte pas le catalogue interne.

### 2.3 `update_stock(item_id: str, quantity_delta: int) → Dict`

- **Thread-safety :** Protégé par `threading.Lock`.
- **Validations :** types str et int (bool exclu), existence du produit, stock résultant ≥ 0.
- **Retour structuré :** `{item_id, previous_stock, delta, new_stock, timestamp}`.

### 2.4 `stream_analytics(metric_name: str, num_events: int = 10) → List[Dict]`

- **Métriques supportées :** `cpu_usage`, `memory_usage`, `request_rate`, `error_rate`.
- **Type de retour :** `List[Dict]` — entièrement sérialisable en JSON.
- **Valeurs :** Déterministes (oscillation linéaire dans l'intervalle de la métrique).

> **IMPORTANT :** `stream_analytics` simule la production d'un flux de métriques au niveau métier, mais ne constitue pas encore un streaming réseau RPC natif. Le protocole Custom RPC actuel est synchrone request/response. La réponse est une liste complète retournée en une seule réponse JSON. Le vrai streaming réseau pourra être étudié ultérieurement dans la partie gRPC si le cahier des charges le prévoit.

---

## 3. Catalogue de démonstration

**DONNÉES DE DÉMONSTRATION UNIQUEMENT** — Non connecté à un véritable système d'inventaire.

| ID | Nom | Catégorie | Prix | Stock initial |
|----|-----|-----------|------|---------------|
| PROD-001 | Laptop ProBook 450 | Electronics | 1299.99 | 42 |
| PROD-002 | Clavier Mécanique RGB | Peripherals | 89.90 | 150 |
| PROD-003 | Câble Ethernet Cat6 (3m) | Networking | 12.50 | 500 |
| PROD-004 | SSD NVMe 1To | Storage | 109.99 | 75 |
| PROD-005 | Écran 27" 4K IPS | Displays | 449.00 | 20 |
| PROD-006 | Module RAM DDR5 16Go | Memory | 64.90 | 200 |

---

## 4. Architecture d'intégration

```text
Service métier (InventoryService)
      ↑
      │ register_method()
      │
RPCServer (Phase 02)
      ↑
      │ TCP + framing 4 octets
      │
RPCClient (Phase 02)
```

Le service métier :
- **N'importe PAS** `socket`, `rpc_core`, `RPCServer`, `RPCClient`.
- **NE dépend PAS** du protocole de transport.
- Est connecté au serveur RPC via `register_method()` dans le point d'intégration (`main.py` ou tests).

---

## 5. Tests

### Résultats

```
Ran 75 tests in 3.040s — OK
```

| Suite | Tests | Réussites | Échecs |
|-------|-------|-----------|--------|
| `test_business.py` — calculate_factorial | 11 | 11 | 0 |
| `test_business.py` — get_product_details | 7 | 7 | 0 |
| `test_business.py` — update_stock | 12 | 12 | 0 |
| `test_business.py` — stream_analytics | 15 | 15 | 0 |
| `test_business.py` — intégration RPC | 7 | 7 | 0 |
| `test_custom_rpc.py` (Phase 02) | 13 | 13 | 0 |
| `test_imports.py` (mis à jour) | 8 | 8 | 0 |
| `test_structure.py` (Phase 01) | 4 | 4 | 0 |
| **TOTAL** | **75** | **75** | **0** |

### Couverture des scénarios

- ✅ Comportement nominal (toutes les méthodes)
- ✅ Validation des types (int, str, bool rejeté)
- ✅ Valeurs limites (n=0, n=200, n=201, stock→0)
- ✅ Erreurs métier (produit inconnu, stock insuffisant, métrique invalide)
- ✅ Thread-safety (50 threads concurrents → résultat cohérent)
- ✅ Isolation de l'état interne (copie des résultats)
- ✅ Sérialisation JSON complète vérifiée
- ✅ Timestamps UTC timezone-aware vérifiés
- ✅ Intégration RPC de bout en bout (RPCClient → TCP → RPCServer → InventoryService)
- ✅ Propagation des erreurs métier via RPC (EXECUTION_ERROR)
- ✅ Transparence de localisation (stub dynamique)

---

## 6. Fichiers modifiés/créés

| Action | Fichier |
|--------|---------|
| **Modifié** | `business/inventory_service.py` |
| **Créé** | `tests/test_business.py` |
| **Modifié** | `tests/test_imports.py` |
| **Créé** | `docs/phase_03_report.md` |
| **Modifié** | `PROJECT_AUDIT.md` |

---

## 7. Distinction streaming

```text
IMPLÉMENTÉ (Phase 03) :
    Service métier
          ↓
    Simulation de production de métriques (_generate_events)
          ↓
    Collecte en List[Dict]
          ↓
    Réponse JSON unique
          ↓
    Custom RPC request/response synchrone

PAS ENCORE IMPLÉMENTÉ :
    Vrai streaming réseau RPC (multi-réponses)
    → Prévu pour la partie gRPC (Phase ultérieure)
```

---

## 8. Dépendances ajoutées

**Aucune dépendance externe ajoutée.**

Modules stdlib utilisés :
- `threading` (Lock pour thread-safety)
- `datetime` / `timezone` (timestamps UTC)
- `typing` (annotations)

---

## 9. Dette technique Phase 02 (conservée)

Les éléments suivants restent tracés et n'ont PAS été traités en Phase 03 :
1. Test unittest formel de fragmentation TCP (absent).
2. Test unittest dédié à `ConnectionClosedError` (absent).
3. Amélioration de l'arrêt propre des threads clients actifs.
