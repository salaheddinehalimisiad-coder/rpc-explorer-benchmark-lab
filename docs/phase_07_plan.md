# PLAN DE PHASE 07 — FAILURE SIMULATOR / SIMULATION DES PANNES RÉSEAU

**Projet :** RPC Explorer & Benchmark Lab  
**Phase :** 07 — Failure Simulation  
**Date :** 26 septembre 2026  
**Statut :** PLANIFICATION — ATTENTE DE VALIDATION

---

## 1. CONTEXTE ET PRÉREQUIS

### 1.1 État Actuel du Projet

**Phase 06 Validée :**
- ✅ 144/144 tests passent sans régression
- ✅ Benchmark comparatif fonctionnel (Local / Custom RPC / gRPC / REST)
- ✅ Métriques de latence, throughput, payload, concurrence mesurées
- ✅ Sérialisation JSON vs Protobuf comparée expérimentalement
- ✅ Documentation architecture.md et PROJECT_AUDIT.md à jour
- ✅ Commits `93b605d` et `64b69e7` poussés sur `origin/main`
- ✅ Working tree propre et synchronisé

**Composants Disponibles :**
- `rpc_core/` : Custom RPC (client_stub, server_skeleton, serializer, transport)
- `grpc/` : Serveur et client gRPC avec contrat Protobuf
- `rest/` : Serveur Flask REST
- `business/` : Service métier indépendant (InventoryService)
- `benchmark/` : Moteur de benchmark avec adapters
- `protos/` : Contrats IDL Protobuf compilés

**Squelette Existant :**
- `failure_simulator/__init__.py` : Export de `FailureSimulator`
- `failure_simulator/simulator.py` : Classe placeholder avec méthodes `NotImplementedError`

**Tests Existants :**
- Aucun test pour `failure_simulator/` détecté dans `tests/`

---

## 2. OBJECTIF DE LA PHASE 07

### 2.1 Objectif Pédagogique Principal

> **Démontrer expérimentalement que RPC ≠ Appel Local en simulant les pannes typiques des systèmes distribués.**

Le simulateur doit permettre d'observer concrètement :

```
APPEL LOCAL
    ↓
Exécution instantanée
Résultat immédiat
Pas d'erreur réseau

VS

APPEL RPC DISTANT
    ↓
Latence réseau
Timeout possible
Connexion refusée possible
Serveur indisponible possible
Message malformé possible
Déconnexion pendant l'appel
```

### 2.2 Objectifs Fonctionnels

1. **Injection de latence artificielle** : Ajouter un délai configurable (ex: 50ms, 200ms, 500ms) pour observer l'impact sur les benchmarks
2. **Simulation de timeout** : Forcer un délai supérieur au timeout client pour déclencher `TimeoutError`
3. **Simulation de serveur indisponible** : Déclencher `ConnectionRefusedError` ou `ConnectionError`
4. **Simulation de déconnexion** : Fermer la socket pendant un appel pour observer `ConnectionClosedError`
5. **Simulation de message invalide** : Envoyer des données malformées pour tester la désérialisation
6. **Simulation de méthode inconnue** : Appeler une méthode non enregistrée pour tester le dispatcher

### 2.3 Contraintes Architecturales

- **Aucune modification des phases précédentes** : Le simulateur doit s'intégrer sans toucher à `rpc_core/`, `grpc/`, `rest/`, `business/`, `benchmark/`
- **Découplage total** : Le simulateur ne doit pas être couplé aux implémentations spécifiques
- **Déterminisme** : Les scénarios de panne doivent être reproductibles et contrôlables
- **Réversibilité** : Activer/désactiver la simulation sans redémarrer les serveurs si possible
- **Observabilité** : Les effets doivent être mesurables et loggables

---

## 3. PÉRIMÈTRE DE LA PHASE 07

### 3.1 PÉRIMÈTRE IN (Ce qui SERA implémenté)

#### 3.1.1 Composants à Créer

1. **`failure_simulator/latency_injector.py`**
   - Classe `LatencyInjector` pour ajouter un délai configurable
   - Méthode `inject_latency(delay_ms: float)` → `time.sleep(delay_ms / 1000.0)`
   - Mode actif/inactif avec `enable()` / `disable()`

2. **`failure_simulator/network_fault.py`**
   - Classe `NetworkFaultSimulator` pour simuler des pannes réseau
   - Méthodes :
     - `simulate_connection_refused()` : Arrêter temporairement le serveur
     - `simulate_server_crash()` : Fermer brutalement la socket serveur
     - `simulate_timeout()` : Attendre indéfiniment sans répondre

3. **`failure_simulator/message_corruptor.py`**
   - Classe `MessageCorruptor` pour simuler des messages invalides
   - Méthodes :
     - `corrupt_json()` : Envoyer un JSON malformé
     - `corrupt_protobuf()` : Envoyer des bytes invalides
     - `send_unknown_method()` : Appeler une méthode non enregistrée

4. **`failure_simulator/simulator.py` (réécriture complète)**
   - Classe `FailureSimulator` orchestrant les différents types de pannes
   - Configuration centralisée des scénarios
   - Interface unifiée pour activer/désactiver les pannes
   - Logging structuré de chaque panne simulée

5. **`failure_simulator/config.py`**
   - Configuration des scénarios de panne (YAML ou dataclass)
   - Paramètres : délai, type de panne, protocole cible, durée

#### 3.1.2 Tests à Créer

6. **`tests/failure_simulator/test_latency_injector.py`**
   - Vérifier que `inject_latency(100)` ajoute réellement ~100ms
   - Vérifier que `enable()` / `disable()` fonctionne
   - Tester avec différentes valeurs (0ms, 50ms, 200ms, 500ms)

7. **`tests/failure_simulator/test_network_fault.py`**
   - Vérifier que `simulate_connection_refused()` déclenche `ConnectionRefusedError`
   - Vérifier que `simulate_timeout()` déclenche `TimeoutError`
   - Vérifier que `simulate_server_crash()` déclenche `ConnectionClosedError`

8. **`tests/failure_simulator/test_message_corruptor.py`**
   - Vérifier que `corrupt_json()` déclenche une erreur de désérialisation
   - Vérifier que `send_unknown_method()` déclenche `RPCMethodNotFoundError`

9. **`tests/integration/test_failure_scenarios.py`**
   - Scénario complet : Custom RPC avec latence artificielle → mesurer l'impact
   - Scénario complet : gRPC avec timeout → observer l'exception
   - Scénario complet : REST avec serveur indisponible → observer l'erreur

#### 3.1.3 Documentation à Créer

10. **`docs/failure_simulation.md`**
    - Architecture du simulateur
    - Types de pannes simulables
    - Interface d'utilisation
    - Exemples de scénarios
    - Métriques observables

11. **Mise à jour de `docs/architecture.md`**
    - Ajouter la section "8. FAILURE SIMULATION" avec architecture détaillée

12. **Mise à jour de `PROJECT_AUDIT.md`**
    - Documenter l'état de la Phase 07
    - Ajouter les résultats des tests
    - Documenter les décisions architecturales

#### 3.1.4 Intégration avec le Benchmark

13. **`benchmark/benchmark_runner.py` (extension minimale)**
    - Ajouter un paramètre optionnel `failure_simulator: Optional[FailureSimulator]`
    - Permettre l'activation d'un scénario de panne pendant le benchmark
    - Mesurer l'impact de la panne sur les métriques

### 3.2 PÉRIMÈTRE OUT (Ce qui NE sera PAS implémenté dans Phase 07)

❌ **Contract Evolution / Breaking Changes** : Reporté en Phase 10  
❌ **Retry Mechanisms** : Pas d'implémentation de retry automatique dans cette phase  
❌ **Circuit Breaker** : Pattern avancé hors périmètre pédagogique  
❌ **Distributed Tracing** : Observabilité avancée non nécessaire  
❌ **Chaos Engineering avancé** : Limitation aux scénarios pédagogiques de base  
❌ **Interface CLI/Dashboard** : Intégration reportée en Phase 11  
❌ **Simulation de congestion réseau** : Trop complexe pour l'objectif pédagogique  
❌ **Simulation de partition réseau** : Hors périmètre système distribué simple  

---

## 4. ARCHITECTURE DU FAILURE SIMULATOR

### 4.1 Vue d'Ensemble

```
┌─────────────────────────────────────────────┐
│         FAILURE SIMULATOR                   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │    FailureSimulator                 │   │
│  │    (Orchestrateur Central)          │   │
│  └──────────┬──────────────────────────┘   │
│             │                               │
│    ┌────────┼────────┐                      │
│    │        │        │                      │
│    ▼        ▼        ▼                      │
│  ┌────┐  ┌────┐  ┌────────┐                │
│  │Lat.│  │Net.│  │Message │                │
│  │Inj.│  │Fault│ │Corrupt.│                │
│  └────┘  └────┘  └────────┘                │
└─────────────────────────────────────────────┘
         │          │          │
         ▼          ▼          ▼
┌──────────────────────────────────────────┐
│   RPC TRANSPORTS                         │
│   • Custom RPC (rpc_core/)               │
│   • gRPC (grpc/)                         │
│   • REST (rest/)                         │
└──────────────────────────────────────────┘
```

### 4.2 Composants Détaillés

#### 4.2.1 LatencyInjector

```python
class LatencyInjector:
    """
    Injecte un délai artificiel dans les appels RPC pour simuler la latence réseau.
    """
    def __init__(self, delay_ms: float = 0.0):
        self.delay_ms = delay_ms
        self.enabled = False
    
    def enable(self, delay_ms: Optional[float] = None):
        """Active l'injection de latence."""
        if delay_ms is not None:
            self.delay_ms = delay_ms
        self.enabled = True
    
    def disable(self):
        """Désactive l'injection de latence."""
        self.enabled = False
    
    def inject(self):
        """Injecte la latence si activée."""
        if self.enabled and self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
```

**Stratégie d'intégration :**
- Le serveur Custom RPC appellera `latency_injector.inject()` avant d'exécuter la méthode métier
- Le serveur gRPC appellera `latency_injector.inject()` dans chaque méthode du servicer
- Le serveur REST appellera `latency_injector.inject()` dans chaque endpoint

**Point d'injection :**
- Ajouter un paramètre optionnel `latency_injector: Optional[LatencyInjector]` aux constructeurs des serveurs
- Si fourni, appeler `latency_injector.inject()` avant l'exécution métier

#### 4.2.2 NetworkFaultSimulator

```python
class NetworkFaultSimulator:
    """
    Simule des pannes réseau et des déconnexions.
    
    DISTINCTION IMPORTANTE:
    - LATENCY: délai artificiel avant traitement (géré par LatencyInjector)
    - TIMEOUT: traitement retardé pour laisser expirer le timeout client
    - CONNECTION_REFUSED: obtenu en n'ayant pas de serveur démarré
    - SERVER_UNAVAILABLE/CRASH: arrêt contrôlé du serveur
    """
    def __init__(self):
        self.fault_type: Optional[str] = None  # "timeout", "crash"
        self.enabled = False
        self.failure_delay: float = 0.0
    
    def simulate_timeout(self, failure_delay_seconds: float = 5.0):
        """
        Configure une simulation de timeout côté serveur.
        Le serveur attendra failure_delay_seconds avant de traiter,
        permettant au client de timeout si son timeout < failure_delay.
        
        Exemple: client_timeout=2.0s, failure_delay=5.0s → TimeoutError
        """
        self.fault_type = "timeout"
        self.failure_delay = failure_delay_seconds
        self.enabled = True
    
    def simulate_server_crash(self):
        """
        Configure une simulation de crash serveur brutal.
        Lève une exception pour fermer la connexion.
        """
        self.fault_type = "crash"
        self.enabled = True
    
    def check_and_apply(self):
        """Vérifie et applique la panne si activée."""
        if not self.enabled:
            return
        
        if self.fault_type == "timeout":
            # Attendre suffisamment longtemps pour que le client timeout
            time.sleep(self.failure_delay)
        elif self.fault_type == "crash":
            raise ConnectionAbortedError("Simulated server crash")
```

**Stratégie d'intégration :**
- Le serveur Custom RPC appellera `network_fault.check_and_apply()` au début du traitement de requête
- Le serveur gRPC appellera `network_fault.check_and_apply()` dans le servicer
- Le serveur REST appellera `network_fault.check_and_apply()` dans les endpoints
- **CONNECTION_REFUSED** sera testé en n'ayant aucun serveur démarré (scénario réel)

#### 4.2.3 MessageCorruptor

```python
class MessageCorruptor:
    """
    Simule des messages invalides ou malformés.
    
    IMPORTANT: La corruption doit être testée au niveau de chaque protocole
    car les erreurs observées diffèrent selon le protocole:
    - Custom RPC (JSON): JSONDecodeError lors de la désérialisation
    - gRPC (Protobuf): grpc.RpcError avec INVALID_ARGUMENT ou INTERNAL
    - REST (JSON/HTTP): 400 Bad Request ou JSONDecodeError
    
    Ne pas promettre une exception identique pour tous les protocoles.
    """
    def __init__(self):
        self.corruption_type: Optional[str] = None
        self.enabled = False
    
    @staticmethod
    def create_invalid_json() -> bytes:
        """Génère un message JSON malformé pour Custom RPC."""
        return b"{invalid json syntax"
    
    @staticmethod
    def create_invalid_protobuf() -> bytes:
        """Génère des bytes invalides pour gRPC Protobuf."""
        return b"\xff\xfe\xfd\xfc\xfb"
    
    @staticmethod
    def create_unknown_method_request() -> Dict[str, Any]:
        """Crée une requête RPC avec une méthode inconnue."""
        return {
            "id": "test_unknown",
            "method": "__invalid_method__",
            "args": {},
            "metadata": {}
        }
```

**Stratégie d'intégration :**
- Utilisé principalement dans les tests pour générer des messages corrompus
- Ne modifie pas directement les serveurs
- Fournit des helpers statiques pour construire des messages invalides
- Les tests vérifieront les erreurs spécifiques à chaque protocole

#### 4.2.4 FailureSimulator (Orchestrateur)

```python
class FailureSimulator:
    """
    Orchestrateur central de simulation de pannes.
    Combine latency_injector et network_fault.
    
    IMPORTANT: Chaque instance est isolée pour éviter la contamination
    entre scénarios. Créer une nouvelle instance pour chaque campagne de test.
    """
    def __init__(self):
        self.latency_injector = LatencyInjector()
        self.network_fault = NetworkFaultSimulator()
        self.active_scenario: Optional[str] = None
    
    def enable_latency_spike(self, delay_ms: float = 200.0):
        """Active une latence artificielle."""
        self.latency_injector.enable(delay_ms)
        self.active_scenario = f"latency_{delay_ms}ms"
    
    def simulate_timeout(self, failure_delay_seconds: float = 5.0):
        """
        Simule un timeout côté serveur.
        Le serveur attendra failure_delay_seconds, permettant au client
        de timeout si son timeout < failure_delay_seconds.
        """
        self.network_fault.simulate_timeout(failure_delay_seconds)
        self.active_scenario = f"timeout_{failure_delay_seconds}s"
    
    def simulate_server_crash(self):
        """Simule un crash serveur."""
        self.network_fault.simulate_server_crash()
        self.active_scenario = "server_crash"
    
    def reset(self):
        """Réinitialise toutes les simulations."""
        self.latency_injector.disable()
        self.network_fault.enabled = False
        self.active_scenario = None
    
    def get_status(self) -> Dict[str, Any]:
        """Retourne l'état actuel du simulateur."""
        return {
            "active_scenario": self.active_scenario,
            "latency_enabled": self.latency_injector.enabled,
            "latency_ms": self.latency_injector.delay_ms,
            "network_fault": self.network_fault.fault_type,
            "failure_delay": self.network_fault.failure_delay if hasattr(self.network_fault, 'failure_delay') else None,
        }
```

**Note sur l'isolation :**
Chaque campagne de panne doit utiliser sa propre instance de `FailureSimulator`
pour éviter qu'un scénario `TIMEOUT` ou `LATENCY` ne contamine le benchmark suivant.

### 4.3 Points d'Intégration avec les Serveurs Existants

#### Option 1 : Injection de Dépendance (RECOMMANDÉE)

Ajouter un paramètre optionnel `failure_simulator` aux constructeurs des serveurs.

**Principe général :**
L'objectif est une **intégration minimale**, pas un nombre exact de lignes.
Chaque serveur (Custom RPC, gRPC, REST) peut avoir un point d'injection différent
selon son architecture.

```python
# Exemple conceptuel pour Custom RPC
class RPCServer:
    def __init__(
        self, 
        host: str = "127.0.0.1", 
        port: int = 5000,
        failure_simulator: Optional['FailureSimulator'] = None
    ):
        self.failure_simulator = failure_simulator
        # ...
    
    def _handle_request(self, client_sock, addr):
        # Injection de latence si configurée
        if self.failure_simulator:
            if self.failure_simulator.latency_injector.enabled:
                self.failure_simulator.latency_injector.inject()
            
            # Simulation de panne réseau si configurée
            if self.failure_simulator.network_fault.enabled:
                self.failure_simulator.network_fault.check_and_apply()
        
        # Traitement normal de la requête
        # ...
```

**Exemple conceptuel pour gRPC :**
```python
class InventoryServicer(inventory_pb2_grpc.InventoryRPCServiceServicer):
    def __init__(
        self,
        service: Optional[InventoryService] = None,
        server_id: str = "grpc_server_01",
        failure_simulator: Optional['FailureSimulator'] = None
    ):
        self._service = service if service is not None else InventoryService()
        self.server_id = server_id
        self.failure_simulator = failure_simulator
    
    def CalculateFactorial(self, request, context):
        # Point d'injection au début de chaque méthode RPC
        if self.failure_simulator:
            if self.failure_simulator.latency_injector.enabled:
                self.failure_simulator.latency_injector.inject()
            if self.failure_simulator.network_fault.enabled:
                self.failure_simulator.network_fault.check_and_apply()
        
        # Traitement normal...
```

**Exemple conceptuel pour REST :**
```python
def create_app(
    service: Optional[InventoryService] = None,
    failure_simulator: Optional['FailureSimulator'] = None
) -> Flask:
    app = Flask(__name__)
    CORS(app)
    
    svc = service if service is not None else InventoryService()
    app.config["INVENTORY_SERVICE"] = svc
    app.config["FAILURE_SIMULATOR"] = failure_simulator
    
    @app.route("/api/factorial", methods=["POST"])
    def calculate_factorial():
        # Point d'injection au début de l'endpoint
        sim = app.config.get("FAILURE_SIMULATOR")
        if sim:
            if sim.latency_injector.enabled:
                sim.latency_injector.inject()
            if sim.network_fault.enabled:
                sim.network_fault.check_and_apply()
        
        # Traitement normal...
```

**Avantages :**
- ✅ Pas de couplage fort
- ✅ Facilement testable
- ✅ Réversible (si `None`, comportement nominal préservé)
- ✅ Respect du principe d'inversion de dépendance
- ✅ Désactivable sans modifier le comportement nominal

**Point important :**
Le nombre exact de lignes modifiées dépendra de l'architecture spécifique
de chaque serveur. L'objectif est l'intégration minimale, pas un quota de lignes.

#### Option 2 : Proxy Wrapper (ALTERNATIVE)

Créer des wrappers autour des serveurs existants :

```python
class FailureSimulatingRPCServer:
    def __init__(self, server: RPCServer, failure_simulator: FailureSimulator):
        self.server = server
        self.failure_simulator = failure_simulator
    
    # Wrapper des méthodes publiques avec injection de pannes
```

**Avantages :**
- Zéro modification des serveurs existants

**Inconvénients :**
- Complexité supplémentaire
- Duplication de l'interface publique
- Moins naturel pour l'intégration avec le benchmark

#### Décision Architecturale Proposée : **Option 1 (Injection de Dépendance)**

---

## 5. STRATÉGIE D'IMPLÉMENTATION

### 5.1 Ordre de Construction

```
ÉTAPE 1 : Composants de Base
    ↓
latency_injector.py
    ↓
Tests unitaires latency_injector
    ↓
VALIDATION ÉTAPE 1

ÉTAPE 2 : Simulation Réseau
    ↓
network_fault.py
    ↓
Tests unitaires network_fault
    ↓
VALIDATION ÉTAPE 2

ÉTAPE 3 : Corruption de Messages
    ↓
message_corruptor.py
    ↓
Tests unitaires message_corruptor
    ↓
VALIDATION ÉTAPE 3

ÉTAPE 4 : Orchestrateur
    ↓
simulator.py (réécriture)
config.py
    ↓
Tests unitaires simulator
    ↓
VALIDATION ÉTAPE 4

ÉTAPE 5 : Intégration Serveurs
    ↓
Modification minimale RPCServer (injection optionnelle)
Modification minimale gRPC servicer (injection optionnelle)
Modification minimale REST server (injection optionnelle)
    ↓
Tests d'intégration
    ↓
VALIDATION ÉTAPE 5

ÉTAPE 6 : Intégration Benchmark
    ↓
Extension BenchmarkRunner (paramètre optionnel)
Tests benchmark avec pannes
    ↓
VALIDATION ÉTAPE 6

ÉTAPE 7 : Documentation
    ↓
failure_simulation.md
Mise à jour architecture.md
Mise à jour PROJECT_AUDIT.md
    ↓
VALIDATION ÉTAPE 7

ÉTAPE 8 : Démonstration
    ↓
Scénarios de démonstration reproductibles
Rapport de Phase 07
    ↓
VALIDATION FINALE
```

### 5.2 Principe de Développement

- **Un composant à la fois** : Ne jamais développer plusieurs composants simultanément
- **Test immédiat** : Chaque composant doit avoir ses tests unitaires avant de passer au suivant
- **Validation incrémentale** : Chaque étape doit être validée avant de continuer
- **Aucune régression** : Les 144 tests existants doivent toujours passer
- **Modifications minimales** : Limiter les changements aux fichiers existants au strict nécessaire

---

## 6. TESTS ET VALIDATION

### 6.1 Tests Unitaires (minimum requis)

| Composant | Tests | Critères de Succès |
|-----------|-------|-------------------|
| `latency_injector.py` | 5 tests | Vérifier délais 0ms, 50ms, 100ms, 200ms, 500ms avec tolérance ±20% |
| `network_fault.py` | 3 tests | Vérifier comportements timeout et crash |
| `message_corruptor.py` | 3 tests | Vérifier génération de messages corrompus pour chaque protocole |
| `simulator.py` | 6 tests | Vérifier orchestration, enable/disable, reset, status, isolation |

**Total attendu : ~17 tests unitaires supplémentaires**

**Note :** Les tests de latence acceptent une tolérance de ±20% car `time.sleep()` 
dépend du scheduler Python/OS et peut varier selon la charge système.

### 6.2 Tests d'Intégration (minimum requis)

| Scénario | Protocole | Critère de Succès |
|----------|-----------|-------------------|
| Latence artificielle 200ms | Custom RPC | Augmentation de latence ≥180ms (tolérance ±20%) |
| Timeout | Custom RPC | Exception timeout levée (type dépend du protocole) |
| Serveur indisponible | Custom RPC | `ConnectionRefusedError` (serveur non démarré) |
| Message JSON invalide | Custom RPC | Erreur de désérialisation observée |
| Méthode inconnue | Custom RPC | `RPCMethodNotFoundError` levée |
| Benchmark avec latence | Custom RPC | Impact mesurable et documenté |
| Isolation scénarios | Tous | Benchmark sans simulateur = baseline après panne |

**Total attendu : ~7 tests d'intégration supplémentaires**

**Note importante :** 
- Les tests d'intégration ne sont pas des tests de performance absolus
- Les valeurs mesurées dépendent de la machine, de l'OS, et de la charge système
- Les tests vérifient les comportements qualitatifs (exception levée, latence augmentée)
  plutôt que des valeurs absolues
- CONNECTION_REFUSED est testé en n'ayant aucun serveur démarré (scénario réel)

### 6.3 Critères d'Acceptation de la Phase 07

✅ **Implémentation :**
- Tous les composants listés dans "PÉRIMÈTRE IN" sont implémentés
- Le code respecte les conventions du projet (docstrings, type hints)
- Intégration minimale dans les serveurs existants (pas de nombre de lignes imposé)
- Le simulateur est désactivable sans modifier le comportement nominal

✅ **Tests :**
- Tous les nouveaux tests passent (≥24 tests supplémentaires)
- Les 144 tests existants continuent de passer (aucune régression)
- Total attendu : ≥168 tests

✅ **Démonstration :**
- Scénario 1 : Latence artificielle → augmentation mesurable et documentée
- Scénario 2 : Timeout → exception timeout observée
- Scénario 3 : Serveur indisponible → exception connection refused observée
- Scénario 4 : Message invalide → erreur de désérialisation observée
- Scénario 5 : Benchmark comparatif → impact mesuré et documenté
- Scénario 6 : Isolation → baseline restaurée après réinitialisation

✅ **Documentation :**
- `docs/failure_simulation.md` créé et complet
- `docs/architecture.md` section 8 ajoutée
- `PROJECT_AUDIT.md` mis à jour avec état Phase 07
- `docs/phase_07_report.md` rédigé avec mesures réelles observées

✅ **Git :**
- Commits atomiques avec messages conventionnels
- Working tree propre
- Push validé sur `origin/main`
- CI verte (si configurée)

✅ **Principe de Désactivation :**
- Si `failure_simulator=None`, comportement nominal préservé (Phase 01-06)
- Aucun couplage entre le simulateur et les phases précédentes

---

## 7. SCÉNARIOS DE DÉMONSTRATION

### 7.1 Scénario 1 : Impact de la Latence Artificielle

**Objectif :** Démontrer qu'une latence réseau augmente le temps de réponse RPC.

**Protocole :**
1. Lancer serveur Custom RPC sans simulateur
2. Mesurer baseline : 100 appels `calculate_factorial(5)`
3. Lancer serveur Custom RPC avec `latency_injector(200ms)`
4. Mesurer avec latence : 100 appels `calculate_factorial(5)`
5. Comparer les latences moyennes

**Résultat Attendu (exemple indicatif) :**
```
Baseline (sans latence)     : ~X ms (dépend de la machine)
Avec latence 200ms          : ~(X + 200) ms ± tolérance
Delta observé               : ≥ 180ms (tolérance ±20%)
```

**Note :** Les valeurs absolues dépendent de la machine, de l'OS Windows, 
et de la charge système. Ce qui importe est que l'augmentation de latence 
soit mesurable et proche de la valeur injectée.

### 7.2 Scénario 2 : Timeout

**Objectif :** Démontrer qu'un appel RPC peut échouer par timeout alors que le serveur fonctionne.

**Protocole :**
1. Configurer client Custom RPC avec `timeout=2.0s`
2. Configurer serveur avec `network_fault.simulate_timeout(failure_delay=5.0s)`
3. Tenter un appel `calculate_factorial(5)`
4. Observer l'exception timeout

**Résultat Attendu :**
```
Exception levée : socket.timeout, TimeoutError, ou équivalent
Message : contient "timeout" ou "timed out"
Temps écoulé : ≈ 2.0s (timeout client)
```

**Note :** Le type exact d'exception peut varier selon le niveau de la stack réseau.
L'important est qu'une exception timeout soit levée avant que le serveur ne réponde.

### 7.3 Scénario 3 : Serveur Indisponible

**Objectif :** Démontrer qu'un appel RPC échoue si le serveur n'est pas démarré.

**Protocole :**
1. S'assurer qu'aucun serveur n'écoute sur `localhost:5000`
2. Tenter un appel Custom RPC
3. Observer l'exception `ConnectionRefusedError`

**Résultat Attendu :**
```
Exception levée : ConnectionRefusedError
Message : contient "Connection refused" ou équivalent OS
```

**Note :** Ce scénario teste la vraie erreur système (pas de serveur démarré),
pas une simulation artificielle.

### 7.4 Scénario 4 : Benchmark Comparatif avec Latence

**Objectif :** Mesurer l'impact de la latence sur les trois protocoles.

**Protocole :**
1. Benchmark baseline sans latence (1000 itérations)
   - Custom RPC
   - gRPC  
   - REST
2. Benchmark avec latence 100ms (1000 itérations)
   - Custom RPC + latence
   - gRPC + latence
   - REST + latence
3. Comparer les distributions de latence

**Résultat Attendu (exemple indicatif) :**
```
Protocol       | Baseline (mean) | +100ms (mean) | Delta
---------------|-----------------|---------------|-------
Custom RPC     | X₁ ms           | (X₁+100) ms   | ≈+100 ms
gRPC           | X₂ ms           | (X₂+100) ms   | ≈+100 ms
REST           | X₃ ms           | (X₃+100) ms   | ≈+100 ms
```

**Note :** Les valeurs absolues X₁, X₂, X₃ dépendent de la machine.
Ce qui importe est que le delta soit proche de la latence injectée (±20%).
Les résultats réels mesurés seront documentés dans le rapport de phase.

### 7.5 Scénario 5 : Message Invalide

**Objectif :** Démontrer qu'un message malformé déclenche une erreur côté serveur.

**Protocole :**
1. Établir une connexion socket au serveur Custom RPC
2. Envoyer manuellement des bytes invalides : `b"{invalid json"`
3. Observer l'erreur de désérialisation côté serveur

**Résultat Attendu :**
```
Erreur serveur : JSONDecodeError ou équivalent
Log serveur    : contient "Failed to deserialize" ou similaire
```

**Note :** Le type exact d'erreur dépend de l'implémentation du deserializer.

### 7.6 Scénario 6 : Isolation des Scénarios

**Objectif :** Démontrer que les scénarios de panne n'affectent pas les appels suivants.

**Protocole :**
1. Mesurer baseline : 100 appels sans simulateur
2. Activer latence 200ms, mesurer 100 appels
3. Réinitialiser le simulateur (`reset()`)
4. Créer une nouvelle instance de serveur sans simulateur
5. Mesurer à nouveau 100 appels

**Résultat Attendu :**
```
Baseline 1     : X ms
Avec latence   : (X+200) ms
Baseline 2     : X ms (±variance normale)
```

**Note :** Baseline 2 doit être comparable à Baseline 1, démontrant que la simulation
de panne n'a pas contaminé le comportement nominal.

---

## 8. RISQUES ET MITIGATION

### 8.1 Risques Identifiés

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Modification des serveurs casse les tests existants | Moyenne | Élevé | Tests de non-régression obligatoires avant commit |
| Latence artificielle non précise (variance Python/OS) | Élevée | Faible | Accepter une tolérance de ±20% dans les tests |
| Intégration avec gRPC complexe | Moyenne | Moyen | Commencer par Custom RPC, puis étendre à gRPC |
| Simulation de timeout bloque les tests | Moyenne | Moyen | Utiliser des timeouts courts (0.5-2s) dans les tests |
| Environnement CI instable avec timeouts | Faible | Moyen | Documenter la variance attendue, augmenter tolérance |
| Contamination entre scénarios de panne | Moyenne | Moyen | Créer une nouvelle instance de simulateur par campagne |

### 8.2 Plan de Contingence

**Si les modifications des serveurs cassent les tests :**
1. Revenir au dernier commit stable via `git reset --hard`
2. Réévaluer la stratégie d'intégration
3. Proposer l'Option 2 (Proxy Wrapper) en alternative

**Si la latence artificielle est trop imprécise :**
1. Accepter une tolérance de ±20% au lieu de ±10%
2. Documenter la variance dans les tests
3. Utiliser des statistiques (médiane, p50) plutôt que la moyenne

**Si l'intégration avec gRPC est trop complexe :**
1. Limiter la Phase 07 à Custom RPC uniquement
2. Reporter gRPC + REST à une phase ultérieure
3. Valider le principe avec Custom RPC avant extension

---

## 9. DÉPENDANCES

### 9.1 Dépendances Externes (requirements.txt)

Aucune nouvelle dépendance requise. Le simulateur utilise uniquement la bibliothèque standard Python :
- `time` : Pour `time.sleep()` et `time.perf_counter()`
- `socket` : Pour les exceptions réseau
- `typing` : Pour les type hints
- `logging` : Pour l'observabilité

### 9.2 Dépendances Internes

Le simulateur dépend de :
- `rpc_core/` : Pour l'intégration avec Custom RPC
- `grpc/` : Pour l'intégration avec gRPC (optionnelle)
- `rest/` : Pour l'intégration avec REST (optionnelle)
- `benchmark/` : Pour l'intégration avec le moteur de benchmark

Mais ces dépendances sont **unidirectionnelles** : le simulateur dépend des autres modules, mais les autres modules ne dépendent pas du simulateur (injection optionnelle).

---

## 10. CALENDRIER ESTIMÉ

| Étape | Durée Estimée | Cumul |
|-------|---------------|-------|
| ÉTAPE 1 : LatencyInjector + tests | 1h | 1h |
| ÉTAPE 2 : NetworkFaultSimulator + tests | 1.5h | 2.5h |
| ÉTAPE 3 : MessageCorruptor + tests | 1h | 3.5h |
| ÉTAPE 4 : FailureSimulator orchestrateur + tests | 1.5h | 5h |
| ÉTAPE 5 : Intégration serveurs + tests | 2h | 7h |
| ÉTAPE 6 : Intégration benchmark + tests | 1.5h | 8.5h |
| ÉTAPE 7 : Documentation | 1h | 9.5h |
| ÉTAPE 8 : Démonstration + rapport | 1h | 10.5h |

**Durée Totale Estimée : 10-11 heures de développement**

---

## 11. FICHIERS CONCERNÉS

### 11.1 Fichiers à Créer

```
failure_simulator/
├── latency_injector.py          (nouveau)
├── network_fault.py              (nouveau)
├── message_corruptor.py          (nouveau)
├── config.py                     (nouveau)
└── simulator.py                  (réécriture complète)

tests/failure_simulator/
├── __init__.py                   (nouveau)
├── test_latency_injector.py      (nouveau)
├── test_network_fault.py         (nouveau)
├── test_message_corruptor.py     (nouveau)
└── test_simulator.py             (nouveau)

tests/integration/
└── test_failure_scenarios.py     (nouveau)

docs/
├── failure_simulation.md         (nouveau)
└── phase_07_report.md            (nouveau, fin de phase)
```

### 11.2 Fichiers à Modifier (minimalement)

```
rpc_core/server_skeleton.py       (ajout paramètre optionnel + injection conditionnelle)
grpc/grpc_server.py                (ajout paramètre optionnel + injection conditionnelle)
rest/rest_server.py                (ajout paramètre optionnel + injection conditionnelle)
benchmark/benchmark_runner.py     (ajout paramètre optionnel failure_simulator)
docs/architecture.md              (ajout section 8 - Failure Simulation)
PROJECT_AUDIT.md                  (mise à jour état Phase 07)
```

**Note :** Le nombre exact de lignes modifiées dépendra de l'architecture spécifique
de chaque serveur. L'objectif est l'intégration minimale, pas un quota de lignes.
Le principe directeur est : **si `failure_simulator=None`, comportement nominal préservé**.

**Estimation : ~6 fichiers modifiés, ~15 fichiers créés**

---

## 12. DÉCISIONS ARCHITECTURALES

### Décision 1 : Injection de Dépendance vs Proxy Wrapper
**Choisie : Injection de Dépendance**  
**Raison :** Simplicité, testabilité, réversibilité, respect du principe d'inversion de dépendance.

### Décision 2 : Latence Artificielle par `time.sleep()`
**Choisie : `time.sleep(delay_ms / 1000.0)`**  
**Raison :** Simple, déterministe, suffisant pour l'objectif pédagogique. Pas besoin de simuler une vraie latence réseau.

### Décision 3 : Simulation de Timeout par Attente Infinie
**Choisie : `time.sleep(duration)` avec `duration > client_timeout`**  
**Raison :** Plus simple que de manipuler directement les sockets. Le client déclenchera son propre timeout.

### Décision 4 : Pas de Modification du Protocol Custom RPC
**Choisie : Garder le protocole Custom RPC intact**  
**Raison :** Le simulateur s'intègre au niveau serveur, pas au niveau protocole. Respect de la séparation des couches.

### Décision 5 : Pas de Retry Automatique dans Phase 07
**Choisie : Reporter les retry mechanisms à une phase ultérieure ou hors périmètre**  
**Raison :** La Phase 07 doit démontrer les pannes, pas les masquer avec des retry.

---

## 13. MÉTRIQUES DE SUCCÈS

### 13.1 Métriques Quantitatives

- ✅ **Couverture de tests** : ≥90% du code `failure_simulator/`
- ✅ **Nombre de tests** : ≥168 tests (144 existants + ≥24 nouveaux)
- ✅ **Aucune régression** : 144/144 tests existants passent
- ✅ **Latence artificielle mesurable** : Delta ≥95% de la latence configurée (tolérance ±5%)
- ✅ **Exceptions déclenchées** : 100% des scénarios de panne déclenchent l'exception attendue

### 13.2 Métriques Qualitatives

- ✅ **Objectif pédagogique atteint** : Un utilisateur peut observer concrètement la différence entre appel local et appel RPC distant
- ✅ **Découplage respecté** : Les phases précédentes ne sont pas couplées au simulateur
- ✅ **Reproductibilité** : Chaque scénario de démonstration peut être rejoué avec les mêmes résultats (±variance)
- ✅ **Documentation complète** : Un développeur peut comprendre et utiliser le simulateur sans assistance

---

## 14. PROCHAINE PHASE APRÈS VALIDATION

**Phase 08 : Comparaison Expérimentale Avancée**
- Analyse comparative détaillée des résultats de benchmark
- Génération de graphiques de comparaison
- Rapport scientifique des observations

**OU**

**Phase 10 : Contract Evolution (si Phase 08 est fusionnée avec Phase 06)**
- Démonstration de breaking changes dans les contrats Protobuf
- Simulation de version N client vs version N+1 serveur
- Observation des erreurs d'incompatibilité

---

## 15. CONCLUSION DU PLAN

### 15.1 Résumé Exécutif

La Phase 07 consiste à implémenter un **simulateur de pannes réseau pédagogique** permettant de démontrer expérimentalement que **RPC ≠ Appel Local**.

Le simulateur sera composé de trois modules spécialisés (`LatencyInjector`, `NetworkFaultSimulator`, `MessageCorruptor`) orchestrés par un `FailureSimulator` central.

L'intégration se fera par **injection de dépendance optionnelle** dans les serveurs existants, garantissant un **découplage total** et **zéro régression**.

Les scénarios de démonstration permettront d'observer concrètement :
- L'impact de la latence réseau sur les performances
- Les exceptions de timeout
- Les erreurs de connexion refusée
- Les crashs serveur
- Les messages invalides

### 15.2 Périmètre Clair

**IN :**
- Latence artificielle (0ms, 50ms, 100ms, 200ms, 500ms)
- Timeout simulation (délai configurable > timeout client)
- Serveur indisponible (serveur non démarré - scénario réel)
- Crash serveur simulation
- Message invalide simulation (spécifique à chaque protocole)
- Méthode inconnue simulation
- Intégration avec benchmark
- Isolation des scénarios (pas de contamination)
- Tests unitaires et d'intégration complets
- Documentation exhaustive avec mesures réelles

**OUT :**
- Contract evolution (Phase 10)
- Retry mechanisms automatiques
- Circuit breaker
- Distributed tracing
- Chaos engineering avancé
- Interface CLI/Dashboard (Phase 11)
- Congestion/partition réseau réelle

### 15.3 Principes Architecturaux Clés

1. **Désactivation par défaut** : Si `failure_simulator=None`, comportement nominal préservé
2. **Isolation des scénarios** : Chaque campagne utilise une instance isolée
3. **Intégration minimale** : Pas de quota de lignes, juste l'essentiel
4. **Tolérance réaliste** : ±20% pour latence artificielle (variance OS/Python)
5. **Tests qualitatifs** : Vérifier comportements, pas valeurs absolues
6. **Mesures documentées** : Résultats réels mesurés, pas valeurs théoriques

Tous les risques identifiés ont des plans de mitigation.  
La stratégie d'implémentation progressive (une étape à la fois) minimise le risque de régression.  
Les tests de non-régression sont obligatoires avant chaque commit.

### 15.4 Durée Estimée

**10-11 heures de développement**  
Soit environ 1.5-2 jours de travail effectif.

---

## 16. STATUT DU PLAN

**PHASE :** 07 — FAILURE SIMULATION  
**STATUT :** PLANIFICATION TERMINÉE  
**PROCHAINE ACTION :** ATTENTE DE VALIDATION DU RESPONSABLE DU PROJET

**CONDITIONS DE DÉMARRAGE DE L'IMPLÉMENTATION :**
1. ✅ Plan validé explicitement par le responsable du projet
2. ✅ Baseline de 144/144 tests confirmé
3. ✅ Working tree propre et synchronisé
4. ✅ Aucune ambiguïté sur le périmètre IN/OUT

**ENGAGEMENT :**
Une fois validé, l'implémentation suivra **strictement** ce plan sans dérive de périmètre.  
Toute déviation majeure sera signalée et soumise à validation avant exécution.

---

**ARRÊT STRICT — ATTENTE DE VALIDATION DU RESPONSABLE DU PROJET.**

---

*Plan rédigé par : Assistant Claude (Kiro)*  
*Date : 26 septembre 2026*  
*Dépôt : C:\Users\halim\OneDrive\Desktop\SOA_Project*  
*Commit actuel : `64b69e7`*

---

## 17. CORRECTIONS APPLIQUÉES — VERSION 2.0

**Date des corrections :** 26 septembre 2026  
**Suite aux recommandations du responsable du projet**

### ✅ Correction 1 : Intégration Minimale (pas de quota de lignes)

**Avant :** « 1 paramètre + 2 lignes » imposé  
**Après :** « Intégration minimale » - le nombre de lignes dépend de l'architecture de chaque serveur

### ✅ Correction 2 : NetworkFaultSimulator Clarifié

**Avant :** Confusion entre types de pannes  
**Après :** Distinction explicite :
- `LATENCY` : délai avant traitement (LatencyInjector)
- `TIMEOUT` : `failure_delay` configurable > `client_timeout`
- `CONNECTION_REFUSED` : serveur non démarré (scénario réel)
- `SERVER_CRASH` : arrêt contrôlé du serveur

### ✅ Correction 3 : MessageCorruptor Repositionné

**Avant :** Promesse d'exceptions identiques pour tous les protocoles  
**Après :** Helpers statiques générant messages invalides, erreurs spécifiques par protocole :
- Custom RPC (JSON) → `JSONDecodeError`
- gRPC (Protobuf) → `grpc.RpcError` (INVALID_ARGUMENT/INTERNAL)
- REST (HTTP) → 400 Bad Request ou `JSONDecodeError`

### ✅ Correction 4 : Suppression Assertions Expérimentales Absolues

**Avant :** « Appel local au moins un ordre de grandeur plus rapide » (test bloquant)  
**Après :** Mesure et documentation des résultats sans assertion rigide sur les ratios

### ✅ Correction 5 : Valeurs de Latence Indicatives

**Avant :** `~202.5 ms` présenté comme valeur garantie  
**Après :** `~(X + 200) ms ± tolérance` avec tolérance ±20%, résultats indicatifs dépendant de la machine/OS

### ✅ Correction 6 : Timeout Configurable

**Avant :** « attente infinie » (`float('inf')`)  
**Après :** `failure_delay` configurable (ex: 5.0s) > `client_timeout` (ex: 2.0s) pour tests rapides et déterministes

### ✅ Correction 7 : Isolation des Scénarios

**Avant :** Non explicite  
**Après :** Chaque campagne de panne utilise une instance isolée de `FailureSimulator` pour éviter contamination

---

## 18. VALIDATION TECHNIQUE FINALE

**Périmètre IN confirmé :**
- ✅ Injection de latence
- ✅ Simulation contrôlée de timeout/indisponibilité
- ✅ Corruption de messages (spécifique par protocole)
- ✅ Orchestration de scénarios
- ✅ Intégration Custom RPC / gRPC / REST
- ✅ Tests unitaires et intégration
- ✅ Documentation et rapport expérimental
- ✅ Non-régression (144/144 tests)

**Périmètre OUT confirmé :**
- ❌ Retry mechanisms
- ❌ Circuit breaker
- ❌ Tracing distribué
- ❌ Partition/congestion réseau réelle
- ❌ Chaos engineering avancé
- ❌ CLI/UI (Phase 11)

**Principe de désactivation confirmé :**
Si `failure_simulator=None`, comportement nominal préservé (Phases 01-06 inchangées).

---

**STATUT FINAL : VERSION 2.0 CORRIGÉE — PRÊTE POUR VALIDATION ET IMPLÉMENTATION**

**ARRÊT STRICT EN PHASE-GATE — ATTENTE DE VALIDATION TECHNIQUE FINALE.**
