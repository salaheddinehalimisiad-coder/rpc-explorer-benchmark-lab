# RAPPORT DE PHASE 06 — BENCHMARK & COMPARATIF (Custom RPC vs gRPC vs REST vs Local)

**Date :** 26 septembre 2026  
**Phase :** 06 — Banc d'Essai Comparatif & Métriques  
**Statut :** PASS  
**Commit :** *(sera complété après commit)*

---

## 1. Objectifs & Périmètre Réalisé

La Phase 06 implémente le moteur de benchmark comparatif complet du projet **RPC Explorer & Benchmark Lab**. Elle fournit une comparaison empirique, reproductible et scientifiquement équitable entre les 4 approches architecturales :
1. **Local (In-Memory Baseline) :** Appel direct sans transport ni sérialisation.
2. **Custom RPC (Sockets TCP + framing uint32 + JSON) :** Middleware maison.
3. **gRPC (HTTP/2 + Protobuf binaire IDL) :** RPC moderne et contrat strict.
4. **REST (HTTP/1.1 + Flask + JSON) :** Architecture orientée ressources.

### Composants implémentés :
* `benchmark/metrics.py` : Calculs statistiques complets (`BenchmarkResult`) utilisant la bibliothèque standard (`statistics`, `math`).
* `benchmark/adapters/` :
  - `BaseBenchmarkAdapter` : Interface commune avec signatures unifiées.
  - `LocalAdapter` : Encapsule `InventoryService`.
  - `CustomRPCAdapter` : Encapsule `RPCClient`.
  - `GRPCAdapter` : Encapsule `InventoryGRPCClient`.
  - `RESTAdapter` : Encapsule `RestClient`.
* `benchmark/benchmark_runner.py` : Orchestrateur (`BenchmarkRunner`) prenant en charge les campagnes de latence, les comparaisons de payload, le micro-benchmark de sérialisation, les tests de concurrence et l'export tabulaire/JSON.
* `tests/test_benchmark.py` : 11 tests automatisés (statistiques, adaptateurs, payloads, sérialisation, concurrence, suite globale).
* `tests/test_imports.py` : Mise à jour des assertions d'interface.

---

## 2. Résultats Réels des Mesures Expérimentales

> **Avertissement de non-simulation :** Les valeurs ci-dessous proviennent d'une exécution réelle mesurée sur Windows (`time.perf_counter()`, machine locale, 500 itérations par protocole après 50 itérations de warm-up).

### 2.1 Synthèse Comparative de Latence & Débit (`calculate_factorial(5)`)

| Protocole | Min (ms) | Moyenne (ms) | Médiane (ms) | p95 (ms) | p99 (ms) | Écart-type | Débit (RPS) |
|---|---|---|---|---|---|---|---|
| **Local** | **0.0019** | **0.0021** | **0.0020** | **0.0021** | **0.0026** | 0.0009 | **414 112.97** |
| **gRPC** | 1.5487 | **1.9155** | 1.8679 | **2.2698** | 2.4858 | 0.1769 | **521.52** |
| **Custom RPC** | 2.1288 | **9.2387** | 3.6979 | **24.1764** | 26.7786 | 7.3540 | **108.20** |
| **REST** | 4.3655 | **9.7249** | 6.9025 | **25.2624** | 30.4083 | 6.5203 | **102.81** |

#### Enseignements Pédagogiques Clés :
1. **Le Piège de la Transparence :** L'appel local en mémoire prend **~2,1 microsecondes**, soit **~912 fois plus rapide** que le RPC le plus performant (gRPC à 1,91 ms) et **~4 400 fois plus rapide** que Custom RPC. Traiter un appel distant comme un appel local est une illusion d'abstraction coûteuse.
2. **Supériorité de gRPC sur HTTP/2 :** gRPC atteint un débit **~4,8 fois supérieur** à Custom RPC et **~5,1 fois supérieur** à REST, avec une latence moyenne 5 fois plus faible et une gigue (écart-type) remarquablement basse (0,18 ms vs > 6,5 ms).

---

### 2.2 Taille des Payloads Réseau (Octets Bruts)

| Opération | Format | Requête (octets) | Réponse (octets) | Total (octets) | Gain Protobuf vs JSON |
|---|---|---|---|---|---|
| **calculate_factorial** | Custom RPC (JSON) | 160 | 120 | 280 | — |
| | REST (JSON Body) | 8 | 50 | 58 | — |
| | **gRPC (Protobuf)** | **2** | **11** | **13** | **-95.4 %** (vs Custom RPC) |
| **get_product_details** | Custom RPC (JSON) | 175 | 284 | 459 | — |
| | REST (JSON Body) | 0 | 167 | 167 | — |
| | **gRPC (Protobuf)** | **10** | **74** | **84** | **-81.7 %** (vs Custom RPC) |

*Protobuf binaire réduit la consommation de bande passante réseau de plus de **81% à 95%** par rapport à Custom RPC en éliminant les noms de clés répétitifs grâce aux numéros de champs du contrat IDL.*

---

### 2.3 Micro-Benchmark de Sérialisation / Désérialisation (1 000 itérations)

| Format | Encodage (μs/op) | Décodage (μs/op) | Coût Total CPU (μs/op) | Vitesse Relative |
|---|---|---|---|---|
| **JSON** (`json.dumps` / `json.loads`) | 7.100 μs | 4.222 μs | 11.322 μs | 1.0x (référence) |
| **Protobuf** (`SerializeToString` / `ParseFromString`) | **0.452 μs** | **0.425 μs** | **0.878 μs** | **~12.9x plus rapide** |

*La sérialisation binaire Protobuf est quasiment **13 fois plus rapide** en temps CPU que JSON.*

---

### 2.4 Tenue sous Charge Concurrente (gRPC Multi-Workers)

| Workers Concurrents | Total Requêtes | Temps Total (s) | Débit Réel (RPS) | Latence Médiane (ms) | Latence p95 (ms) |
|---|---|---|---|---|---|
| **1 worker** | 50 | 0.0606 s | 825.30 req/s | 1.147 ms | 1.393 ms |
| **5 workers** | 250 | 0.2216 s | 1 127.94 req/s | 4.194 ms | 6.507 ms |
| **10 workers** | 500 | 0.3766 s | **1 327.61 req/s** | 6.242 ms | 11.119 ms |
| **20 workers** | 1 000 | 0.9755 s | 1 025.12 req/s | 12.067 ms | 26.575 ms |

*Le débit maximal sous gRPC est atteint avec 10 workers concurrents (**1 327 req/s**). À 20 workers, la contention thread commence à augmenter la latence p95 sans gain de débit supplémentaire.*

---

### 3. Résultats Réels de la Suite Complète des Tests

```text
Ran 144 tests in 6.838s

OK
```

#### Répartition des 144 tests :
* `test_structure.py` : 4 tests (PASS)
* `test_imports.py` : 8 tests (PASS, actualisé pour Benchmark)
* `test_custom_rpc.py` : 13 tests (PASS)
* `test_business.py` : 50 tests (PASS)
* `test_grpc.py` : 30 tests (PASS)
* `test_rest.py` : 28 tests (PASS)
* `test_benchmark.py` : **11 tests (PASS, NOUVEAU)**
  - Exactitude statistique (moyenne, médiane, écart-type, percentiles p50/p90/p95/p99, RPS, error_rate)
  - Intégrité des 4 adaptateurs (Local, Custom RPC, gRPC, REST)
  - Mesure des tailles de payloads
  - Micro-benchmark de sérialisation
  - Concurrence multi-workers
  - Suite complète et export tabulaire

---

### 4. Fichiers Modifiés et Créés

| Action | Fichier | Rôle |
|---|---|---|
| **Créé** | `benchmark/metrics.py` | Conteneur `BenchmarkResult` et calculs statistiques stdlib |
| **Modifié** | `benchmark/adapters/base_adapter.py` | Interface commune pour adaptateurs |
| **Créé** | `benchmark/adapters/local_adapter.py` | Adaptateur pour appel direct en mémoire |
| **Créé** | `benchmark/adapters/custom_rpc_adapter.py` | Adaptateur Custom RPC |
| **Créé** | `benchmark/adapters/grpc_adapter.py` | Adaptateur gRPC |
| **Créé** | `benchmark/adapters/rest_adapter.py` | Adaptateur REST |
| **Modifié** | `benchmark/adapters/__init__.py` | Export des adaptateurs |
| **Modifié** | `benchmark/benchmark_runner.py` | Implémentation complète de l'orchestrateur |
| **Modifié** | `benchmark/__init__.py` | Export de `BenchmarkRunner`, `BenchmarkResult` |
| **Créé** | `tests/test_benchmark.py` | Suite de tests du banc d'essai |
| **Modifié** | `tests/test_imports.py` | Actualisation des assertions d'import |
| **Créé** | `docs/phase_06_report.md` | Rapport détaillé avec données expérimentales réelles |
| **Modifié** | `PROJECT_AUDIT.md` | Actualisation de la checklist et du statut d'audit global |

---

### 5. Bilan & État du Dépôt

- **Zéro régression :** Les 133 tests existants continuent de passer avec succès.
- **Périmètre préservé :** `business/`, `rpc_core/`, `grpc/`, `protos/`, `rest/`, `failure_simulator/`, `under_the_hood/`, `cli/` sont strictement intacts.
- **Indépendance vis-à-vis de bibliothèques lourdes :** Les calculs statistiques et la collecte reposent sur la bibliothèque standard Python (`statistics`, `math`, `time`).
