# ARCHITECTURE — RPC EXPLORER & BENCHMARK LAB

**Projet :** Démonstrateur Pédagogique des Remote Procedure Calls  
**Version :** 1.0  
**Date :** 25 septembre 2026

---

## 1. VISION GÉNÉRALE

Le projet **RPC Explorer & Benchmark Lab** est un laboratoire pédagogique permettant de comprendre, expérimenter et comparer les mécanismes des **Remote Procedure Calls (RPC)** dans les systèmes distribués.

### Objectif Principal

> Transformer les concepts théoriques du RPC en phénomènes observables, mesurables et expérimentables.

### Portée Fonctionnelle

Le système doit permettre de :

1. **Comprendre** le cycle complet d'un appel RPC (client → stub → sérialisation → transport → serveur → dispatcher → exécution → réponse)
2. **Comparer** trois approches RPC : Custom (from scratch), gRPC (Protobuf), REST (HTTP/JSON)
3. **Mesurer** les performances (latence, throughput, taille des payloads)
4. **Observer** les mécanismes internes (mode "Under the Hood")
5. **Expérimenter** avec les pannes réseau (latence, timeout, déconnexion)
6. **Démontrer** l'évolution des contrats et les problèmes de compatibilité

---

## 2. ARCHITECTURE LOGIQUE

### 2.1 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI / DASHBOARD                         │
│                    (Interface Utilisateur)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
   ┌────────┐  ┌─────────┐  ┌─────────┐
   │ Custom │  │  gRPC   │  │  REST   │
   │  RPC   │  │         │  │         │
   └────┬───┘  └────┬────┘  └────┬────┘
        │           │            │
        │      ┌────┴────┐       │
        │      │ Protobuf│       │
        │      │ (IDL)   │       │
        │      └────┬────┘       │
        │           │            │
        ▼           ▼            ▼
   ┌─────────────────────────────────┐
   │   TRANSPORT LAYER               │
   │   • TCP Socket (Custom)         │
   │   • HTTP/2 (gRPC)              │
   │   • HTTP/1.1 (REST)            │
   └────────────┬────────────────────┘
                │
                ▼
   ┌─────────────────────────────────┐
   │   SERVER LAYER                  │
   │   • Custom RPC Server           │
   │   • gRPC Server                 │
   │   • REST Server                 │
   └────────────┬────────────────────┘
                │
                ▼
   ┌─────────────────────────────────┐
   │   BUSINESS LAYER                │
   │   Service de Calcul &           │
   │   Gestion d'Inventaire          │
   └─────────────────────────────────┘
```

### 2.2 Séparation des Responsabilités

Le projet respecte une séparation claire entre les couches :

```
┌─────────────────────────────────────┐
│  INTERFACE LAYER                    │  ← CLI, Dashboard, Menus
├─────────────────────────────────────┤
│  ADAPTER LAYER                      │  ← Adaptateurs RPC (Custom, gRPC, REST)
├─────────────────────────────────────┤
│  PROTOCOL LAYER                     │  ← Stubs, Serialization, Dispatcher
├─────────────────────────────────────┤
│  TRANSPORT LAYER                    │  ← Socket, HTTP/2, HTTP/1.1
├─────────────────────────────────────┤
│  SERVER LAYER                       │  ← Serveurs RPC
├─────────────────────────────────────┤
│  BUSINESS LAYER                     │  ← Logique métier (indépendante du RPC)
└─────────────────────────────────────┘
```

**Principe fondamental :** Le service métier ne connaît pas les protocoles RPC. Les protocoles exposent le service métier.

---

## 3. APPROCHE 1 : RPC CUSTOM (FROM SCRATCH)

### 3.1 Objectif Pédagogique

Le RPC custom permet de comprendre ce qu'un framework RPC réalise derrière une abstraction de haut niveau.

### 3.2 Architecture RPC Custom

```
CLIENT
  │
  ├─→ CLIENT STUB
  │     │
  │     ├─→ Method Call (Transparency)
  │     │
  │     └─→ SERIALIZER
  │           │
  │           └─→ JSON Encoding
  │                 │
  │                 └─→ TRANSPORT (TCP Socket)
  │                       │
  │                       └─→ NETWORK
  │
SERVER
  │
  ├─→ RECEIVER
  │     │
  │     └─→ DESERIALIZER
  │           │
  │           └─→ JSON Decoding
  │                 │
  │                 └─→ DISPATCHER / SKELETON
  │                       │
  │                       ├─→ Method Lookup
  │                       │
  │                       ├─→ Validation
  │                       │
  │                       └─→ EXECUTION
  │                             │
  │                             └─→ Business Function
  │                                   │
  │                                   └─→ RESULT
  │                                         │
  │                                         └─→ SERIALIZER
  │                                               │
  │                                               └─→ TRANSPORT
  │                                                     │
  │                                                     └─→ CLIENT
```

### 3.3 Composants RPC Custom

#### `rpc_core/serializer.py`
Responsabilité : Encoder/Décoder les requêtes et réponses RPC

**Format de requête :**
```json
{
  "id": "unique_request_id",
  "method": "calculate_factorial",
  "args": {"n": 5},
  "metadata": {
    "timestamp": "2026-09-25T10:30:00Z",
    "client_id": "client_001"
  }
}
```

**Format de réponse :**
```json
{
  "id": "unique_request_id",
  "result": 120,
  "error": null,
  "metadata": {
    "server_id": "server_001",
    "execution_time_ms": 2.5
  }
}
```

#### `rpc_core/client_stub.py`
Responsabilité : Fournir une abstraction d'appel transparent

**Interface cible :**
```python
client = RPCClient(host="localhost", port=5000)
result = client.call("calculate_factorial", n=5)
# Transparence : ressemble à un appel local
```

**Derrière l'appel :**
1. Sérialisation de la requête
2. Envoi via socket TCP
3. Attente de la réponse
4. Désérialisation du résultat
5. Retour du résultat

#### `rpc_core/server_skeleton.py`
Responsabilité : Dispatcher les appels RPC vers les fonctions métier

**Mécanisme :**
1. Écoute sur un socket TCP
2. Réception des requêtes
3. Désérialisation
4. Validation du nom de méthode (table blanche)
5. Lookup de la fonction correspondante
6. Exécution
7. Sérialisation du résultat
8. Envoi de la réponse

**Sécurité :** Seules les méthodes explicitement enregistrées peuvent être appelées.

```python
ALLOWED_METHODS = {
    "calculate_factorial": calculate_factorial,
    "get_product_details": get_product_details,
    "update_stock": update_stock,
}
```

---

## 4. APPROCHE 2 : gRPC (PROTOBUF)

### 4.1 Objectif Pédagogique

gRPC permet de démontrer un RPC moderne basé sur un contrat IDL (Interface Definition Language) strict.

### 4.2 Architecture gRPC

```
DÉVELOPPEUR
  │
  └─→ FICHIER .proto (IDL)
        │
        └─→ protoc (Compilateur Protobuf)
              │
              ├─→ GENERATED CLIENT STUB
              │
              └─→ GENERATED SERVER SKELETON
                    │
                    ├─→ CLIENT
                    │     │
                    │     └─→ gRPC Call (Unary / Streaming)
                    │           │
                    │           └─→ Protobuf Serialization (Binary)
                    │                 │
                    │                 └─→ HTTP/2 Transport
                    │
                    └─→ SERVER
                          │
                          └─→ gRPC Server
                                │
                                ├─→ Protobuf Deserialization
                                │
                                └─→ Business Function
                                      │
                                      └─→ Response
```

### 4.3 Composants gRPC

#### `protos/inventory.proto`
Contrat IDL définissant les services et les messages

**Exemple de définition :**
```protobuf
syntax = "proto3";

package inventory;

service InventoryService {
  // Unary RPC
  rpc GetProductDetails(ProductRequest) returns (ProductResponse);
  
  // Server Streaming RPC
  rpc StreamAnalytics(AnalyticsRequest) returns (stream AnalyticsEvent);
}

message ProductRequest {
  string product_id = 1;
}

message ProductResponse {
  string product_id = 1;
  string name = 2;
  int32 stock = 3;
  double price = 4;
}
```

#### `grpc/grpc_server.py`
Implémentation du serveur gRPC

**Responsabilités :**
1. Implémenter les services définis dans le `.proto`
2. Démarrer le serveur gRPC
3. Exposer les fonctions métier via gRPC

#### `grpc/grpc_client.py`
Client gRPC généré et utilisé pour les appels

**Types d'appels supportés :**
- **Unary RPC** : 1 requête → 1 réponse
- **Server Streaming** : 1 requête → N réponses (stream)

---

## 5. APPROCHE 3 : REST (HTTP/JSON)

### 5.1 Objectif Pédagogique

REST sert de référence comparative pour démontrer les différences avec RPC.

### 5.2 Architecture REST

```
CLIENT
  │
  └─→ HTTP Request (GET/POST/PUT/DELETE)
        │
        ├─→ Endpoint: /api/products/{id}
        │
        └─→ JSON Serialization
              │
              └─→ HTTP/1.1 Transport
                    │
                    └─→ REST SERVER
                          │
                          ├─→ Routing
                          │
                          ├─→ JSON Deserialization
                          │
                          └─→ Business Function
                                │
                                └─→ JSON Response
```

### 5.3 Composants REST

#### `rest/rest_server.py`
Serveur HTTP exposant des endpoints REST

**Endpoints prévus :**
```
GET    /api/products/{id}      → get_product_details
POST   /api/products/{id}/stock → update_stock
GET    /api/calculate/factorial → calculate_factorial
```

#### `rest/rest_client.py`
Client HTTP pour les appels REST

---

## 6. COUCHE MÉTIER (BUSINESS LAYER)

### 6.1 Principe d'Indépendance

La couche métier est **complètement indépendante** des protocoles RPC.

**Elle ne connaît pas :**
- Custom RPC
- gRPC
- REST
- Socket
- HTTP
- Protobuf
- JSON

**Elle fournit uniquement :**
- Fonctions métier pures
- Logique de calcul
- Gestion de données

### 6.2 Service Métier : Calcul & Gestion d'Inventaire

#### `business/inventory_service.py`

**Fonctions métier :**

```python
def calculate_factorial(n: int) -> int:
    """Calcule la factorielle de n."""
    pass

def get_product_details(product_id: str) -> dict:
    """Retourne les détails d'un produit."""
    pass

def update_stock(item_id: str, quantity: int) -> dict:
    """Met à jour le stock d'un produit."""
    pass

def stream_analytics() -> Iterator[dict]:
    """Génère des événements analytiques (pour streaming)."""
    pass
```

**Caractéristiques :**
- Fonctions synchrones et simples
- Pas de dépendance réseau
- Testables indépendamment
- Pas de gestion du transport

---

## 7. BENCHMARK ENGINE

### 7.1 Objectif

Comparer expérimentalement les trois approches RPC sur des métriques objectives.

### 7.2 Architecture Benchmark

```
BENCHMARK RUNNER
  │
  ├─→ CONFIGURATION
  │     │
  │     ├─→ Nombre d'itérations
  │     ├─→ Warm-up
  │     ├─→ Payload size
  │     └─→ Protocoles à tester
  │
  ├─→ ADAPTERS
  │     │
  │     ├─→ CustomRPCAdapter
  │     ├─→ GRPCAdapter
  │     └─→ RESTAdapter
  │
  ├─→ EXECUTION
  │     │
  │     ├─→ Warm-up Phase
  │     ├─→ Measurement Phase
  │     └─→ Metrics Collection
  │
  └─→ RESULTS
        │
        ├─→ Latency (mean, median, p50, p95, p99)
        ├─→ Throughput
        ├─→ Payload Size
        ├─→ Error Rate
        └─→ Comparison Report
```

### 7.3 Métriques Collectées

| Métrique | Description | Unité |
|----------|-------------|-------|
| **Latency (mean)** | Temps moyen d'un appel RPC | ms |
| **Latency (median)** | Médiane du temps d'appel | ms |
| **p50, p95, p99** | Percentiles de latence | ms |
| **Throughput** | Nombre de requêtes/seconde | req/s |
| **Payload Size** | Taille des messages | bytes |
| **Error Rate** | Taux d'échec | % |
| **Serialization Time** | Temps de sérialisation | ms |

### 7.4 Conditions Expérimentales

Pour garantir la comparabilité :
- **Même machine** : Tests sur localhost
- **Même opération** : `calculate_factorial(5)`
- **Même nombre d'itérations** : 1000 requêtes
- **Warm-up** : 100 requêtes avant mesure
- **Conditions réseau** : Sans latence artificielle (baseline)

---

## 8. FAILURE SIMULATION (PHASE 07 - VALIDÉE)

### 8.1 Objectif Pédagogique

Démontrer que **RPC ≠ Appel Local** en simulant les pannes typiques des systèmes distribués :
- Un appel local en mémoire s'exécute immédiatement sans dépendre d'une socket ou d'un réseau.
- Un appel RPC ou REST traverse un réseau exposé aux déconnexions, timeouts, délais artificiels et corruptions.

### 8.2 Architecture des Composants

```
┌─────────────────────────────────────────────────────────────┐
│                    FAILURE SIMULATOR                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │     FailureSimulator (Orchestrateur Central)          │  │
│  │     - Isolation stricte des scénarios (pas de fuite)  │  │
│  │     - Application des FailureConfig presets           │  │
│  │     - Réinitialisation propre via reset()             │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │                               │
│         ┌───────────────────┼───────────────────┐           │
│         ▼                   ▼                   ▼           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │LatencyInjector│   │NetworkFault  │    │Message       │   │
│  │              │    │Simulator     │    │Corruptor     │   │
│  │- delay_ms    │    │- timeout     │    │- bad JSON    │   │
│  │- enable()    │    │- crash       │    │- bad Protobuf│   │
│  │- disable()   │    │- reset()     │    │- bit-flip    │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 Modules Implémentés

- **`failure_simulator/latency_injector.py`** : injection de délai artificiel (`delay_ms`) via `time.sleep()`.
- **`failure_simulator/network_fault.py`** : simulation de timeouts (rétention serveur) et de crashs brutaux (`ConnectionAbortedError`).
- **`failure_simulator/message_corruptor.py`** : fabrique de requêtes invalides (JSON corrompu, octets Protobuf incompatibles, méthode inconnue).
- **`failure_simulator/config.py`** : dataclasses et presets standardisés (`nominal`, `latency_50ms`, `latency_200ms`, `timeout_3s`, `server_crash`).
- **`failure_simulator/simulator.py`** : orchestrateur central avec méthode `apply_pre_execution_hooks()` et statut temps réel.

### 8.4 Matrice de Comportement Comparatif

| Scénario | Appel Local | Custom RPC | gRPC | REST |
|---|---|---|---|---|
| **Latence (+50ms)** | Instantané | Latence +53ms | Latence +53ms | Latence +52ms |
| **Timeout (Client 0.2s, Serveur 1s)** | Impossible | `TimeoutError` (~208ms) | `StatusCode.DEADLINE_EXCEEDED` (~218ms) | `RestClientError` (~217ms) |
| **Serveur Éteint** | Impossible | `ConnectionError` | `StatusCode.UNAVAILABLE` | `RestClientError` (Conn refused) |
| **Crash Serveur Brutal** | Impossible | `ConnectionError` | `StatusCode.UNAVAILABLE` | `HTTP 503 SERVER_UNAVAILABLE` |
| **Message Malformé** | Impossible | `INVALID_REQUEST_FORMAT` | `DecodeError` / `RpcError` | `HTTP 400 Bad Request` |
| **Méthode Inconnue** | `AttributeError` | `METHOD_NOT_FOUND` | `StatusCode.UNIMPLEMENTED` | `HTTP 404 Not Found` |

---

## 9. UNDER THE HOOD (MODE PÉDAGOGIQUE)

### 9.1 Objectif

Rendre visible chaque étape du cycle RPC pour des fins pédagogiques.

### 9.2 Informations Capturées

```
┌────────────────────────────────────────┐
│ CLIENT                                 │
│ Method: calculate_factorial            │
│ Args: {"n": 5}                         │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ STUB                                   │
│ Generating RPC request...              │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ SERIALIZATION                          │
│ Format: JSON                           │
│ Serialized Request:                    │
│ {"id":"req_001","method":"calculate_   │
│  factorial","args":{"n":5}}            │
│ Size: 87 bytes                         │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ TRANSPORT                              │
│ Protocol: TCP                          │
│ Host: localhost                        │
│ Port: 5000                             │
│ Sending...                             │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ SERVER                                 │
│ Request received                       │
│ Timestamp: 2026-09-25T10:30:15.234Z    │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ DISPATCHER                             │
│ Method: calculate_factorial            │
│ Validation: ✓ Method allowed           │
│ Args: {"n": 5}                         │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ BUSINESS FUNCTION                      │
│ Executing: calculate_factorial(5)      │
│ Result: 120                            │
│ Execution Time: 0.05ms                 │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ SERIALIZATION (RESPONSE)               │
│ Format: JSON                           │
│ Response: {"id":"req_001","result":120}│
│ Size: 35 bytes                         │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ CLIENT                                 │
│ Response received                      │
│ Result: 120                            │
│ Total Latency: 2.5ms                   │
└────────────────────────────────────────┘
```

---

## 10. CONTRACT EVOLUTION

### 10.1 Objectif Pédagogique

Démontrer les problèmes de compatibilité lorsqu'un contrat RPC évolue.

### 10.2 Scénario Pédagogique

#### **Version 1 du Contrat**
```protobuf
message ProductResponse {
  string product_id = 1;
  string name = 2;
  int32 stock = 3;
}
```

**Client V1** ↔ **Server V1** → ✅ **SUCCESS**

#### **Version 2 du Contrat (Breaking Change)**
```protobuf
message ProductResponse {
  string product_id = 1;
  string name = 2;
  int32 stock = 3;
  double price = 4;  // ← Nouveau champ obligatoire
  string category = 5; // ← Nouveau champ obligatoire
}
```

**Client V1** ↔ **Server V2** → ⚠️ **INCOMPATIBILITÉ**

**Observation attendue :**
- Client V1 ne sait pas gérer les nouveaux champs
- Désérialisation échoue ou champs ignorés
- Comportement inattendu

### 10.3 Implémentation

Branche dédiée ou répertoire séparé pour tester l'évolution de contrat sans casser la branche principale.

---

## 11. CLI / DASHBOARD

### 11.1 Objectif

Fournir une interface permettant d'interagir avec tous les composants du système.

### 11.2 Fonctionnalités

```
RPC EXPLORER & BENCHMARK LAB
═════════════════════════════════════════

1. Sélectionner le protocole
   • Custom RPC
   • gRPC
   • REST

2. Appeler une méthode
   • calculate_factorial
   • get_product_details
   • update_stock
   • stream_analytics

3. Mode Under the Hood
   • Activer/Désactiver

4. Lancer un Benchmark
   • Configuration (iterations, warm-up)
   • Protocoles à comparer
   • Génération du rapport

5. Simuler des Pannes
   • Latence artificielle (0ms - 500ms)
   • Timeout
   • Déconnexion

6. Visualiser les Logs
   • Client
   • Server
   • RPC Protocol
   • Errors

7. Contract Evolution Demo
   • Version N
   • Version N+1
   • Observation des incompatibilités
```

---

## 12. ARBORESCENCE DU PROJET

```
SOA_Project/
│
├── CLAUDE.md                    # Master Prompt
├── PROJECT_AUDIT.md             # Rapport d'audit
├── README.md                    # Documentation principale
├── requirements.txt             # Dépendances Python
├── .gitignore                   # Fichiers à ignorer
├── main.py                      # Point d'entrée CLI
│
├── docs/                        # Documentation
│   ├── architecture.md          # Ce fichier
│   ├── custom-rpc.md            # Documentation RPC Custom
│   ├── grpc.md                  # Documentation gRPC
│   └── benchmarking.md          # Méthodologie de benchmark
│
├── rpc_core/                    # RPC Custom (From Scratch)
│   ├── __init__.py
│   ├── serializer.py            # JSON Encoder/Decoder
│   ├── client_stub.py           # Client RPC Custom
│   └── server_skeleton.py       # Serveur RPC Custom
│
├── grpc/                        # gRPC Implementation
│   ├── __init__.py
│   ├── grpc_server.py           # Serveur gRPC
│   └── grpc_client.py           # Client gRPC
│
├── protos/                      # Protobuf Definitions
│   └── inventory.proto          # IDL Protobuf
│
├── rest/                        # REST Implementation
│   ├── __init__.py
│   ├── rest_server.py           # Serveur REST
│   └── rest_client.py           # Client REST
│
├── business/                    # Business Layer
│   ├── __init__.py
│   └── inventory_service.py     # Fonctions métier
│
├── benchmark/                   # Benchmark Engine
│   ├── __init__.py
│   ├── benchmark_runner.py      # Runner principal
│   ├── metrics.py               # Collecte de métriques
│   └── adapters/                # Adaptateurs RPC
│       ├── __init__.py
│       ├── custom_rpc_adapter.py
│       ├── grpc_adapter.py
│       └── rest_adapter.py
│
├── failure_simulator/           # Simulation de Pannes
│   ├── __init__.py
│   ├── latency_injector.py      # Injection de latence
│   ├── timeout_simulator.py     # Simulation de timeout
│   └── network_failure.py       # Simulation de déconnexion
│
├── under_the_hood/              # Mode Pédagogique
│   ├── __init__.py
│   └── visualizer.py            # Visualisation du cycle RPC
│
├── cli/                         # Interface CLI
│   ├── __init__.py
│   └── menu.py                  # Menu interactif
│
└── tests/                       # Tests
    ├── __init__.py
    ├── test_rpc_custom.py       # Tests RPC Custom
    ├── test_grpc.py             # Tests gRPC
    ├── test_rest.py             # Tests REST
    ├── test_benchmark.py        # Tests Benchmark
    └── test_integration.py      # Tests d'intégration
```

---

## 13. DÉCISIONS ARCHITECTURALES

### DA-001 : Séparation stricte du service métier
**Décision :** Le service métier ne doit connaître aucun protocole RPC.

**Justification :** Permet de tester la logique métier indépendamment et de démontrer clairement la séparation des responsabilités.

### DA-002 : JSON pour le RPC Custom
**Décision :** Utiliser JSON pour la sérialisation du RPC custom.

**Justification :** Simple, lisible, pédagogique. Permet de comparer avec Protobuf (binaire) et REST (JSON également).

### DA-003 : TCP Socket pour le RPC Custom
**Décision :** Utiliser des sockets TCP bruts pour le transport custom.

**Justification :** Démontre le transport au niveau le plus bas. Permet de comprendre ce que HTTP/2 et gRPC font derrière l'abstraction.

### DA-004 : Table blanche pour le dispatcher
**Décision :** Seules les méthodes explicitement enregistrées peuvent être appelées.

**Justification :** Sécurité. Évite l'exécution arbitraire de code.

### DA-005 : Benchmark avec warm-up
**Décision :** Toujours effectuer un warm-up avant les mesures de benchmark.

**Justification :** Évite les biais dus au JIT, à la mise en cache, ou au cold start.

### DA-006 : Localhost pour les benchmarks
**Décision :** Les benchmarks sont exécutés sur localhost.

**Justification :** Élimine la variabilité réseau. Permet de mesurer uniquement l'overhead du protocole RPC.

### DA-007 : Pas de base de données persistante
**Décision :** Le service métier utilise des données en mémoire ou mockées.

**Justification :** Le projet est un démonstrateur RPC, pas un système CRUD complet. Évite la complexité inutile.

---

## 14. CONTRAINTES TECHNIQUES

### CT-001 : Python 3.8+
Le projet doit fonctionner avec Python 3.8 ou supérieur.

### CT-002 : Dépendances minimales
Limiter les dépendances externes au strict nécessaire :
- `grpcio` et `grpcio-tools` pour gRPC
- `protobuf` pour Protobuf
- Framework HTTP léger (Flask ou FastAPI) pour REST
- `pytest` pour les tests

### CT-003 : Reproductibilité
Tous les benchmarks doivent être reproductibles avec les mêmes conditions expérimentales documentées.

### CT-004 : Testabilité
Chaque composant doit pouvoir être testé indépendamment.

### CT-005 : Observabilité
Le mode "Under the Hood" doit pouvoir être activé/désactivé sans modifier le code source.

---

## 15. ÉVOLUTIONS FUTURES (HORS SCOPE PHASE 01)

### Améliorations Possibles

- **Sécurité** : TLS/SSL pour les communications
- **Authentification** : Tokens, OAuth2
- **Load Balancing** : Plusieurs instances de serveur
- **Service Discovery** : Enregistrement dynamique des services
- **Monitoring** : Prometheus, Grafana
- **Tracing Distribué** : OpenTelemetry
- **Client Streaming** : gRPC bidirectionnel
- **Circuit Breaker** : Gestion avancée des pannes
- **Compression** : gzip, Brotli pour les payloads
- **Versioning API** : Gestion multi-versions du contrat

**Note :** Ces améliorations ne seront ajoutées que si elles apportent une réelle valeur pédagogique au projet.

---

## 16. RÉFÉRENCES

- **gRPC Documentation** : https://grpc.io/docs/
- **Protocol Buffers** : https://protobuf.dev/
- **RFC 7231 (HTTP)** : https://tools.ietf.org/html/rfc7231
- **JSON-RPC 2.0** : https://www.jsonrpc.org/specification
- **Martin Fowler - Microservices** : https://martinfowler.com/articles/microservices.html

---

**FIN DE L'ARCHITECTURE — VERSION 1.0**
