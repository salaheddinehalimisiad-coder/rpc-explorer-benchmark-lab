# RPC Explorer & Benchmark Lab

**Démonstrateur Pédagogique des Remote Procedure Calls**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Educational-green.svg)](LICENSE)

---

## 🎯 Objectif du Projet

Ce projet est un **laboratoire pédagogique** permettant de comprendre, expérimenter, observer et comparer les mécanismes des **Remote Procedure Calls (RPC)** dans les systèmes distribués.

> **Vision :** Transformer les concepts théoriques du RPC en phénomènes observables, mesurables et expérimentables.

---

## 🧩 Fonctionnalités Principales

### 1. **RPC Custom (From Scratch)**
Implémentation d'un mini-framework RPC pour comprendre les mécanismes fondamentaux :
- Client Stub
- Sérialisation JSON
- Transport TCP Socket
- Server Skeleton
- Dispatcher
- Gestion des erreurs

### 2. **gRPC (Protobuf)**
Utilisation de gRPC pour démontrer un RPC moderne basé sur IDL :
- Contrat Protobuf (`.proto`)
- Génération de code
- Appels Unary RPC
- Server Streaming
- Sérialisation binaire haute performance

### 3. **REST (HTTP/JSON)**
Implémentation REST pour comparaison :
- Endpoints HTTP
- Sérialisation JSON
- API RESTful classique

### 4. **Benchmark Comparatif**
Mesure et comparaison des performances :
- Latence (mean, median, p50, p95, p99)
- Throughput (req/s)
- Taille des payloads
- Taux d'erreur

### 5. **Mode "Under the Hood"**
Visualisation pédagogique du cycle RPC complet :
```
CLIENT → STUB → SERIALIZATION → TRANSPORT → SERVER → DISPATCHER → EXECUTION → RESPONSE
```

### 6. **Simulation de Pannes**
Expérimentation avec les défaillances réseau :
- Injection de latence artificielle
- Simulation de timeout
- Déconnexion réseau
- Serveur indisponible

### 7. **Contract Evolution**
Démonstration des problèmes de compatibilité :
- Version N vs Version N+1
- Breaking changes
- Impact sur les clients

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           CLI / DASHBOARD               │
└────────────┬────────────────────────────┘
             │
   ┌─────────┼─────────┐
   │         │         │
   ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Custom │ │  gRPC  │ │  REST  │
│  RPC   │ │        │ │        │
└────┬───┘ └───┬────┘ └───┬────┘
     │         │          │
     └─────────┼──────────┘
               │
               ▼
    ┌──────────────────────┐
    │   Business Service   │
    │  Calcul & Inventory  │
    └──────────────────────┘
```

**Consultez [`docs/architecture.md`](docs/architecture.md) pour l'architecture complète.**

---

## 📦 Structure du Projet

```
SOA_Project/
├── rpc_core/              # RPC Custom (from scratch)
│   ├── serializer.py      # Sérialisation JSON
│   ├── client_stub.py     # Client RPC
│   └── server_skeleton.py # Serveur RPC
│
├── grpc/                  # gRPC Implementation
│   ├── grpc_server.py
│   └── grpc_client.py
│
├── protos/                # Contrats Protobuf
│   └── inventory.proto
│
├── rest/                  # REST Implementation
│   ├── rest_server.py
│   └── rest_client.py
│
├── business/              # Logique métier (indépendante)
│   └── inventory_service.py
│
├── benchmark/             # Benchmark Engine
│   ├── benchmark_runner.py
│   └── adapters/
│
├── failure_simulator/     # Simulation de pannes
│
├── under_the_hood/        # Visualisation pédagogique
│
├── cli/                   # Interface CLI
│
├── tests/                 # Tests unitaires et d'intégration
│
└── docs/                  # Documentation
```

---

## 🚀 Installation

### Prérequis

- Python 3.8 ou supérieur
- pip

### Installation des dépendances

```bash
# Cloner le dépôt
git clone https://github.com/votre-username/SOA_Project.git
cd SOA_Project

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt

# Générer les stubs gRPC (Protobuf)
python -m grpc_tools.protoc -I./protos --python_out=./grpc --grpc_python_out=./grpc ./protos/inventory.proto
```

---

## 🎮 Utilisation

### Lancer le CLI Interactif

```bash
python main.py
```

### Menu Principal

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

3. Mode Under the Hood (ON/OFF)

4. Lancer un Benchmark

5. Simuler des Pannes

6. Visualiser les Logs

7. Contract Evolution Demo

0. Quitter
```

### Exemples de Commandes

#### Démarrer le serveur RPC Custom
```bash
python rpc_core/server_skeleton.py
```

#### Appeler une méthode via le client Custom RPC
```bash
python rpc_core/client_stub.py --method calculate_factorial --args '{"n": 5}'
```

#### Démarrer le serveur gRPC
```bash
python grpc/grpc_server.py
```

#### Lancer un benchmark comparatif
```bash
python main.py --benchmark --iterations 1000 --protocols custom,grpc,rest
```

#### Simuler une latence de 200ms
```bash
python main.py --simulate-latency 200
```

---

## 🧪 Tests

### Lancer tous les tests

```bash
pytest tests/
```

### Lancer les tests d'un module spécifique

```bash
pytest tests/test_rpc_custom.py
pytest tests/test_grpc.py
pytest tests/test_benchmark.py
```

### Coverage

```bash
pytest --cov=rpc_core --cov=grpc --cov=rest --cov=business tests/
```

---

## 📊 Benchmark

### Méthodologie

Les benchmarks comparent les trois approches RPC sur des métriques objectives :

| Métrique | Description |
|----------|-------------|
| **Latence moyenne** | Temps moyen d'un appel RPC |
| **Médiane** | Latence médiane (p50) |
| **p95, p99** | Percentiles de latence |
| **Throughput** | Nombre de requêtes/seconde |
| **Payload Size** | Taille des messages sérialisés |
| **Error Rate** | Taux d'échec |

### Conditions Expérimentales

- **Machine** : localhost (élimination de la variabilité réseau)
- **Opération** : `calculate_factorial(5)`
- **Itérations** : 1000 requêtes
- **Warm-up** : 100 requêtes avant mesure
- **Protocoles** : Custom RPC, gRPC, REST

**Note :** Les résultats sont spécifiques aux conditions expérimentales et ne constituent pas des conclusions universelles.

### Exemple de Rapport

```
BENCHMARK REPORT
═══════════════════════════════════════════════════════════

Conditions:
  • Iterations: 1000
  • Warm-up: 100
  • Operation: calculate_factorial(5)
  • Environment: localhost, Python 3.10

Results:
┌─────────────┬──────────┬────────────┬───────────┬───────────┐
│ Protocol    │ Mean (ms)│ Median (ms)│ p95 (ms)  │ p99 (ms)  │
├─────────────┼──────────┼────────────┼───────────┼───────────┤
│ Custom RPC  │   2.5    │    2.3     │    3.8    │    5.2    │
│ gRPC        │   1.8    │    1.7     │    2.9    │    4.1    │
│ REST        │   4.2    │    3.9     │    6.5    │    8.7    │
└─────────────┴──────────┴────────────┴───────────┴───────────┘

Payload Size:
  • Custom RPC (JSON): 87 bytes
  • gRPC (Protobuf):   42 bytes
  • REST (JSON):       95 bytes
```

---

## 🔬 Mode "Under the Hood"

Ce mode permet de visualiser chaque étape du cycle RPC :

```
CLIENT
  ├─→ Method: calculate_factorial
  └─→ Args: {"n": 5}

STUB
  └─→ Generating RPC request...

SERIALIZATION
  ├─→ Format: JSON
  ├─→ Serialized: {"id":"req_001","method":"calculate_factorial","args":{"n":5}}
  └─→ Size: 87 bytes

TRANSPORT
  ├─→ Protocol: TCP
  ├─→ Host: localhost:5000
  └─→ Sending...

SERVER
  └─→ Request received at 2026-09-25T10:30:15.234Z

DISPATCHER
  ├─→ Method: calculate_factorial
  ├─→ Validation: ✓ Method allowed
  └─→ Args: {"n": 5}

BUSINESS FUNCTION
  ├─→ Executing: calculate_factorial(5)
  ├─→ Result: 120
  └─→ Execution Time: 0.05ms

RESPONSE
  ├─→ Serialized: {"id":"req_001","result":120}
  ├─→ Size: 35 bytes
  └─→ Total Latency: 2.5ms
```

---

## 💥 Simulation de Pannes

Le projet permet de simuler les défaillances typiques des systèmes distribués :

### Latence Artificielle
```bash
python main.py --simulate-latency 200  # 200ms de latence
```

### Timeout
```bash
python main.py --simulate-timeout 5  # Timeout après 5 secondes
```

### Serveur Indisponible
```bash
# Arrêter le serveur et observer le comportement client
```

### Objectif Pédagogique

Démontrer que **RPC ≠ Appel Local** :
- Latence réseau
- Timeouts
- Indisponibilité
- Erreurs de sérialisation
- Incompatibilités de contrat

---

## 📚 Documentation

- [`docs/architecture.md`](docs/architecture.md) — Architecture complète du système
- [`docs/custom-rpc.md`](docs/custom-rpc.md) — Documentation du RPC Custom
- [`docs/grpc.md`](docs/grpc.md) — Documentation gRPC
- [`docs/benchmarking.md`](docs/benchmarking.md) — Méthodologie de benchmark

---

## 🛠️ Technologies Utilisées

- **Python 3.8+**
- **gRPC** — Framework RPC moderne
- **Protocol Buffers** — Sérialisation binaire
- **JSON** — Sérialisation texte (RPC Custom, REST)
- **TCP Sockets** — Transport bas niveau (RPC Custom)
- **HTTP/2** — Transport gRPC
- **HTTP/1.1** — Transport REST
- **pytest** — Framework de tests

---

## 🎓 Objectifs Pédagogiques

Ce projet permet de comprendre :

1. **Comment fonctionne un appel RPC ?**
   - Client → Stub → Sérialisation → Transport → Serveur → Dispatcher → Exécution

2. **Pourquoi RPC ≠ Appel Local ?**
   - Latence réseau
   - Sérialisation/Désérialisation
   - Pannes possibles (timeout, déconnexion)
   - Incompatibilités de contrat

3. **Différences entre Custom RPC, gRPC et REST**
   - Protocoles de transport
   - Formats de sérialisation
   - Performances
   - Complexité

4. **Comment mesurer les performances d'un système distribué ?**
   - Méthodologie de benchmark
   - Métriques pertinentes
   - Conditions expérimentales

5. **Comment gérer les pannes dans un système distribué ?**
   - Timeout
   - Retry
   - Circuit Breaker
   - Observabilité

---

## 📋 Roadmap

État au 26 septembre 2026, d'après les rapports `docs/phase_XX_report.md` et [`PROJECT_AUDIT.md`](PROJECT_AUDIT.md). Suite de tests : **188/188 PASS** (`python -m pytest`).

### Phase 00 — Audit du projet ✅ TERMINÉE
- [x] Audit initial du dépôt ([`PROJECT_AUDIT.md`](PROJECT_AUDIT.md))

### Phase 01 — Architecture & Structure ✅ TERMINÉE ([rapport](docs/phase_01_report.md))
- [x] Arborescence du projet
- [x] Documentation architecturale ([`docs/architecture.md`](docs/architecture.md))
- [x] Environnement de développement (`pyproject.toml`, `requirements.txt`)
- [x] Git & .gitignore
- [x] README

### Phase 02 — Custom RPC Core ✅ TERMINÉE ([rapport](docs/phase_02_report.md))
- [x] Serializer JSON
- [x] Transport TCP avec framing par longueur
- [x] Client Stub
- [x] Server Skeleton / Dispatcher
- [x] Tests unitaires et d'intégration

### Phase 03 — Service Métier ✅ TERMINÉE ([rapport](docs/phase_03_report.md))
- [x] Fonctions métier (`InventoryService` : factorielle, produits, stock, analytics)
- [x] Tests indépendants du transport

### Phase 04 — gRPC ✅ TERMINÉE ([rapport](docs/phase_04_report.md))
- [x] Contrat Protobuf (`protos/inventory.proto`)
- [x] Serveur gRPC
- [x] Client gRPC
- [x] Streaming

### Phase 05 — REST ✅ TERMINÉE ([rapport](docs/phase_05_report.md))
- [x] Serveur REST (Flask)
- [x] Client REST
- [x] Endpoints

### Phase 06 — Benchmark Engine ✅ TERMINÉE ([rapport](docs/phase_06_report.md))
- [x] Runner (`benchmark/benchmark_runner.py`)
- [x] Métriques (`benchmark/metrics.py`)
- [x] Comparaison Local / Custom RPC / gRPC / REST

### Phase 07 — Failure Simulation ✅ TERMINÉE ([rapport](docs/phase_07_report.md))
- [x] Latence artificielle
- [x] Timeout
- [x] Déconnexion / serveur indisponible
- [x] Corruption de messages

### Under the Hood (À VENIR)
- [ ] Visualisation du cycle RPC (`under_the_hood/tracer.py` est encore un squelette)

### CLI / Dashboard (À VENIR)
- [ ] Menu interactif (`cli/cli_runner.py` est encore un squelette)
- [ ] Interface utilisateur

### Contract Evolution (À VENIR)
- [ ] Versioning
- [ ] Breaking changes

> La numérotation des phases restantes n'est pas encore fixée.

---

## 🤝 Contribution

Ce projet est à vocation pédagogique. Les contributions sont les bienvenues pour :

- Améliorer la clarté pédagogique
- Corriger des bugs
- Ajouter des tests
- Améliorer la documentation

**Règles de contribution :**
1. Une fonctionnalité = une branche
2. Tests obligatoires
3. Documentation mise à jour
4. Code review requis

---

## 📄 Licence

Ce projet est sous licence **Éducative**. Il est destiné à des fins pédagogiques et académiques.

---

## 👨‍💻 Auteur

**Halim**  
Projet de Fin d'Études — Systèmes Distribués & RPC

---

## 📞 Contact

Pour toute question ou suggestion :
- Email : boulahia.yacinesaid@gmail.com
- GitHub Issues : [Créer une issue](https://github.com/votre-username/SOA_Project/issues)

---

## 🌟 Remerciements

Merci aux frameworks et outils open-source qui ont rendu ce projet possible :
- **gRPC** et **Protocol Buffers** (Google)
- **Python** Community
- **pytest** Team

---

**« Comprendre RPC, c'est comprendre les systèmes distribués. »**
