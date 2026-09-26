# RAPPORT OFFICIEL DE FIN DE PHASE 07 — FAILURE SIMULATOR & ROBUSTESSE

**Projet :** RPC Explorer & Benchmark Lab  
**Phase :** 07 — Failure Simulator / Simulation des Pannes Réseau  
**Date :** 26 septembre 2026  
**Auteur :** Antigravity AI Assistant  
**Statut :** TERMINE — 100% VALIDE  

---

## 1. Contexte et Objectifs de la Phase 07

L'objectif central de la Phase 07 était de **démontrer expérimentalement que RPC ≠ Appel Local** en soumettant les différents transports (Appel Local, Custom RPC, gRPC, REST) à des conditions de défaillance réelles et reproductibles :
- Délais et pics de latence réseau
- Dépassement de délais d'attente (timeouts)
- Arrêt ou crash brutal du serveur distant
- Corruption de flux et messages syntaxiquement invalides
- Appels de méthodes non déclarées

### Périmètre Respecté :
- **IN :**
  - Module `failure_simulator/latency_injector.py`
  - Module `failure_simulator/network_fault.py`
  - Module `failure_simulator/message_corruptor.py`
  - Module `failure_simulator/config.py`
  - Orchestrateur central `failure_simulator/simulator.py`
  - Intégration minimale par injection optionnelle (`failure_simulator=None` par défaut)
  - 44 nouveaux tests (unitaires + intégration réseau)
  - Script d'expérimentation réelle `failure_simulator/run_failure_demo.py`
  - Documentation dédiée `docs/failure_simulation.md` et mise à jour de l'architecture.
- **OUT (Strictement exclu) :**
  - Retry mechanisms automatiques
  - Circuit Breakers
  - Tracing distribué (Phase 09)
  - Contract Breaking Changes IDL (Phase 10)
  - Interface CLI interactive (Phase 11)

---

## 2. Synthèse de la Suite de Tests

| Suite de Tests | Nombre de Tests | Résultat |
|---|---|---|
| **Baseline Phase 01–06 (Non-régression)** | 144 | 144/144 OK (100%) |
| `tests/test_latency_injector.py` | 8 | 8/8 OK |
| `tests/test_network_fault.py` | 5 | 5/5 OK |
| `tests/test_message_corruptor.py` | 6 | 6/6 OK |
| `tests/test_simulator.py` | 12 | 12/12 OK |
| `tests/test_failure_scenarios.py` (Intégration) | 13 | 13/13 OK |
| **TOTAL GÉNÉRAL** | **188** | **188/188 OK (100%)** |

Durée totale d'exécution de la suite complète : **~9.88s** sur Python 3.13 / Windows.

---

## 3. Résultats Expérimentaux Réels Mesurés

Toutes les données ci-dessous proviennent d'exécutions réelles sur la machine locale enregistrées dans `failure_simulator/experiment_results.json` :

### 3.1 Mesure de l'Impact de la Latence Injectée (30 itérations par point)

| Transport | 0ms (Nominal) | +50ms injectés | Delta mesuré | +100ms injectés | Delta mesuré |
|---|---|---|---|---|---|
| **Custom RPC** | Médiane: **1.83 ms** (Moy: 6.47 ms) | Médiane: **54.97 ms** (Moy: 60.20 ms) | **+53.14 ms** | Médiane: **104.93 ms** (Moy: 109.51 ms) | **+103.10 ms** |
| **gRPC** | Médiane: **1.30 ms** (Moy: 1.32 ms) | Médiane: **54.49 ms** (Moy: 54.42 ms) | **+53.19 ms** | Médiane: **103.97 ms** (Moy: 103.95 ms) | **+102.67 ms** |
| **REST** | Médiane: **9.76 ms** (Moy: 13.74 ms) | Médiane: **62.44 ms** (Moy: 64.61 ms) | **+52.68 ms** | Médiane: **112.20 ms** (Moy: 113.31 ms) | **+102.44 ms** |

**Observation scientifique :**
L'injection de latence via `LatencyInjector` applique une translation quasi-parfaite (+53ms pour 50ms demandés, +103ms pour 100ms demandés), le surcoût de ~3ms correspondant à la granularité du planificateur système Windows (`time.sleep`).

### 3.2 Comportement Face aux Timeouts (Client timeout = 0.2s, Rétention serveur = 1.0s)

| Transport | Exception / Code Observé | Temps d'attente client avant coupure |
|---|---|---|
| **Custom RPC** | `TimeoutError: timed out` | **207.8 ms** |
| **gRPC** | `grpc.RpcError: StatusCode.DEADLINE_EXCEEDED` | **217.8 ms** |
| **REST** | `RestClientError: Read timed out` | **217.4 ms** |

**Observation scientifique :**
Chaque client coupe la connexion immédiatement dès que son échéance (200ms) est atteinte, protégeant ainsi l'appelant d'un blocage indéfini causé par un serveur distant lent ou figé.

### 3.3 Comportement Face au Crash Serveur Brutal

| Transport | Erreur Côté Client | Description du Comportement |
|---|---|---|
| **Custom RPC** | `ConnectionError` / `ConnectionClosedError` | La socket TCP est fermée côté serveur, provoquant une lecture de 0 octets côté client stub. |
| **gRPC** | `grpc.RpcError` (`StatusCode.UNAVAILABLE`) | Le canal HTTP/2 détecte l'interruption de la frame de flux et renvoie le statut `UNAVAILABLE`. |
| **REST** | `RestClientError: HTTP 503 (SERVER_UNAVAILABLE)` | Le serveur renvoie un code standard 503 Service Unavailable signalant l'incapacité à traiter. |

### 3.4 Comportement Face aux Messages Corrompus

| Scénario | Transport | Comportement Observé |
|---|---|---|
| **JSON malformé** | Custom RPC | Serveur renvoie une réponse d'erreur cadrée `INVALID_REQUEST_FORMAT` (`JSONDecodeError`) |
| **Octets Protobuf invalides** | gRPC | Échec de désérialisation binaire (`google.protobuf.message.DecodeError`) |
| **Méthode inconnue** | Custom RPC | Erreur structurée `METHOD_NOT_FOUND` via la table blanche du dispatcher |
| **Endpoint inexistant** | REST | Réponse HTTP `404 Not Found` |

### 3.5 Démonstration d'Isolation (Non-contamination)

- Appel initial nominal : **21.57 ms**
- Appel sous pic de latence (+50ms) : **68.29 ms**
- Appel après réinitialisation `sim.reset()` : **12.00 ms** (retour instantané aux performances de référence).

---

## 4. Invariants d'Intégrité Vérifiés

1. **Règle du non-faux-code** : Aucune métrique n'a été inventée. Toutes les mesures proviennent du runner réel.
2. **Préservation du nominal** : `failure_simulator=None` sur tous les serveurs par défaut ⇒ comportement nominal strictement inchangé (144/144 tests d'origine intacts).
3. **Zéro dépendance nouvelle** : Utilisation exclusive de la bibliothèque standard (`time`, `socket`, `typing`, `dataclasses`, `statistics`, `json`).
4. **Découplage architectural** : Les serveurs n'ont reçu qu'un point d'injection optionnel et un hook de pré-exécution d'une ligne.

---

## 5. Fichiers Modifiés et Créés

### Fichiers Créés :
- `failure_simulator/latency_injector.py`
- `failure_simulator/network_fault.py`
- `failure_simulator/message_corruptor.py`
- `failure_simulator/config.py`
- `failure_simulator/run_failure_demo.py`
- `failure_simulator/experiment_results.json`
- `tests/test_latency_injector.py`
- `tests/test_network_fault.py`
- `tests/test_message_corruptor.py`
- `tests/test_simulator.py`
- `tests/test_failure_scenarios.py`
- `docs/failure_simulation.md`
- `docs/phase_07_report.md`

### Fichiers Modifiés :
- `failure_simulator/__init__.py` (exports publics)
- `failure_simulator/simulator.py` (réécriture complète de l'orchestrateur)
- `rpc_core/server_skeleton.py` (injection optionnelle de `failure_simulator`)
- `grpc/grpc_server.py` (injection optionnelle de `failure_simulator`)
- `rest/rest_server.py` (injection optionnelle de `failure_simulator`)
- `benchmark/benchmark_runner.py` (support optionnel de `failure_simulator`)
- `tests/test_imports.py` (mise à jour pour Phase 07)
- `docs/architecture.md` (ajout Section 8)
- `PROJECT_AUDIT.md` (mise à jour statut Phase 07)

---

## 6. Conclusion et Clôture de la Phase 07

La **Phase 07 — Failure Simulator** est intégralement achevée et validée avec succès.  
Le projet dispose à présent d'un ensemble complet d'outils d'injection d'anomalies permettant de tester, mesurer et illustrer concrètement la fragilité et les caractéristiques des appels réseau distribués comparativement aux appels locaux en mémoire.
