# FAILURE SIMULATOR — SIMULATION DES PANNES RÉSEAU (PHASE 07)

**Projet :** RPC Explorer & Benchmark Lab  
**Composant :** `failure_simulator/`  
**Statut :** Validé & Fonctionnel (Phase 07)  

---

## 1. Objectif Pédagogique Principal

> **Démontrer expérimentalement que RPC ≠ Appel Local en simulant les défaillances caractéristiques des environnements distribués.**

Dans un appel local en mémoire :
- L'exécution est synchrone et quasi-instantanée (~0.001 ms).
- Il n'y a aucun délai de transit, aucun risque de paquet perdu, aucun timeout réseau.
- L'appel ne peut pas échouer avec une interruption de câble ou un serveur éteint.

À l'inverse, dans un appel distant (RPC/REST) :
- Les données traversent une pile réseau et des buffers TCP/HTTP.
- Le réseau introduit une latence variable (RTT, jitter, contention).
- Le serveur distant peut s'interrompre brutalement pendant le traitement (`ConnectionAbortedError`, `UNAVAILABLE`, `503`).
- Le serveur peut tarder à répondre, entraînant un dépassement de délai côté client (`TimeoutError`, `DEADLINE_EXCEEDED`).
- Les charges utiles peuvent être corrompues ou tronquées (`JSONDecodeError`, `DecodeError`, `400 Bad Request`).

---

## 2. Architecture du Module

```
┌─────────────────────────────────────────────────────────────┐
│                    FAILURE SIMULATOR                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │     FailureSimulator (Orchestrateur Central)          │  │
│  │     - Isolation des scénarios (pas de contamination)  │  │
│  │     - Gestion des profils via FailureConfig           │  │
│  │     - Réinitialisation propre (reset())               │  │
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
         │                    │                   │
         ▼                    ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Custom RPC       │ │ gRPC             │ │ REST             │
│ (TCP/JSON)       │ │ (HTTP/2/Protobuf)│ │ (HTTP/JSON)      │
│ server_skeleton  │ │ grpc_server      │ │ rest_server      │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

### 2.1 Composants Détaillés

1. **`LatencyInjector` (`failure_simulator/latency_injector.py`)** :
   - Injecte un délai configurable (`delay_ms`) via `time.sleep()`.
   - Méthodes : `enable(delay_ms)`, `disable()`, `inject()`.
   - Si désactivé ou délai nul : exécution immédiate (< 0.05 ms).

2. **`NetworkFaultSimulator` (`failure_simulator/network_fault.py`)** :
   - Simule les pannes au niveau du transport.
   - `simulate_timeout(failure_delay_seconds)` : retarde la réponse pour laisser expirer le timeout du client.
   - `simulate_server_crash()` : lève `ConnectionAbortedError` pour couper brutalement la connexion TCP/HTTP.
   - `disable()` : désactive toute panne.

3. **`MessageCorruptor` (`failure_simulator/message_corruptor.py`)** :
   - Utilitaires statiques pour produire des charges utiles malformées :
     - `create_invalid_json()` : syntaxe JSON cassée.
     - `create_truncated_json()` : payload tronqué simulant une coupure mi-flux.
     - `create_invalid_protobuf()` : octets incompatibles avec les messages IDL.
     - `create_unknown_method_request()` : requête RPC avec méthode non enregistrée.
     - `corrupt_bytes(data, offset)` : altération bit-à-bit d'octets.

4. **`FailureSimulator` (`failure_simulator/simulator.py`)** :
   - Orchestre l'ensemble des modules ci-dessus.
   - Fournit le hook unifié `apply_pre_execution_hooks()`.
   - Chaque instance est isolée pour empêcher la contamination entre campagnes.
   - Si `failure_simulator=None` sur un serveur, le comportement nominal est 100% préservé.

5. **`FailureConfig` (`failure_simulator/config.py`)** :
   - Dataclass de configuration avec presets prêts à l'emploi (`PRESET_NOMINAL`, `PRESET_LATENCY_50MS`, `PRESET_LATENCY_200MS`, `PRESET_TIMEOUT_3S`, `PRESET_SERVER_CRASH`).

---

## 3. Matrice Comparative des Comportements en Cas de Panne

| Type de Panne | Appel Local | Custom RPC (TCP/JSON) | gRPC (HTTP/2/Protobuf) | REST (HTTP/JSON) |
|---|---|---|---|---|
| **Latence Réseau (ex: 50ms)** | Aucun impact (exécution immédiate) | Latence mesurée augmentée de ~50ms | Latence mesurée augmentée de ~50ms | Latence mesurée augmentée de ~50ms |
| **Timeout Client** | Impossible (en mémoire) | `TimeoutError` (client socket timeout) | `grpc.RpcError` (`StatusCode.DEADLINE_EXCEEDED`) | `RestClientError` / `requests.Timeout` |
| **Serveur Éteint / Non Démarré** | Impossible | `ConnectionError` (`Connection refused`) | `grpc.RpcError` (`StatusCode.UNAVAILABLE`) | `RestClientError` (`Failed to establish connection`) |
| **Crash Brutal du Serveur** | Impossible | `ConnectionError` / `ConnectionClosedError` | `grpc.RpcError` (`StatusCode.UNAVAILABLE`) | `RestClientError` (`HTTP 503 SERVER_UNAVAILABLE`) |
| **Message / Payload Corrompu** | Impossible | `INVALID_REQUEST_FORMAT` (`JSONDecodeError`) | `grpc.RpcError` / `DecodeError` | `HTTP 400 Bad Request` |
| **Méthode Inconnue** | `AttributeError` immédiat | `METHOD_NOT_FOUND` (table blanche) | `StatusCode.UNIMPLEMENTED` | `HTTP 404 Not Found` |

---

## 4. Résultats Expérimentaux Réels Mesurés

Toutes les métriques ci-dessous ont été mesurées expérimentalement sur la machine hôte via `run_failure_demo.py` :

### 4.1 Injection de Latence (Médiane mesurée sur 30 appels)

| Scénario | Custom RPC | gRPC | REST |
|---|---|---|---|
| **Baseline nominale (0ms)** | 1.83 ms | 1.30 ms | 9.76 ms |
| **Injection +50ms** | 54.97 ms (Delta: +53.14 ms) | 54.49 ms (Delta: +53.19 ms) | 62.44 ms (Delta: +52.68 ms) |
| **Injection +100ms** | 104.93 ms (Delta: +103.10 ms) | 103.97 ms (Delta: +102.67 ms) | 112.20 ms (Delta: +102.44 ms) |

### 4.2 Déclenchement Réel des Timeouts (Client timeout = 0.2s, Serveur delay = 1.0s)

- **Custom RPC** : `TimeoutError` levée après **207.8 ms**
- **gRPC** : `grpc.RpcError` (`StatusCode.DEADLINE_EXCEEDED`) levée après **217.8 ms**
- **REST** : `RestClientError` (Read timed out) levée après **217.4 ms**

### 4.3 Déclenchement Réel des Crashs Serveur

- **Custom RPC** : Rupture immédiate du socket TCP capturée côté client (`ConnectionError`)
- **gRPC** : Canal notifié avec le code standard `StatusCode.UNAVAILABLE`
- **REST** : Réponse HTTP immédiate `503 Service Unavailable` (`SERVER_UNAVAILABLE`)

### 4.4 Isolation et Réversibilité

- Appel initial nominal : **21.57 ms**
- Appel avec injection de 50ms : **68.29 ms**
- Appel après `sim.reset()` : **12.00 ms** (retour immédiat aux performances nominales).
