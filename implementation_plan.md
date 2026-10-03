# Plan d'implémentation — correspondance avec l'énoncé

Ce fichier répond à l'énoncé *« Feuille de route : Démonstrateur & Framework d'Exploration RPC »* (`SOA_project.pdf`), qui demande un `implementation_plan.md` à la racine.
Il reprend l'énoncé **section par section, point par point**, et indique pour chacun : où c'est implémenté, comment le voir tourner, et quel test automatique le vérifie.

Légende : ✅ fait et testé · ⚠️ fait autrement que l'énoncé (raison donnée) · ➕ ajouté en plus de l'énoncé.

Toutes les commandes se lancent depuis la racine du projet. `python -m pytest -q` exécute les 269 tests (Linux, Python 3.13 ; la version précédente, 246 tests, est vérifiée sous Windows, Python 3.10).

---

## 1. Contexte & Objectif

| Exigence de l'énoncé | État | Où / comment |
|---|---|---|
| 1. Comprendre les rouages internes : stub client, marshalling/sérialisation, transport réseau, squelette/dispatcher serveur, démarshalling | ✅ | `rpc_core/client_stub.py` (stub), `rpc_core/serializer.py` + `rpc_core/protocol.py` (marshalling), `rpc_core/transport.py` (TCP), `rpc_core/server_skeleton.py` (dispatcher). Chaque étape est affichée par `python main.py --under-the-hood` et dessinée dans la vue *Appel* du tableau de bord. Tests : `tests/test_custom_rpc.py`, `tests/test_under_the_hood.py` |
| 2a. RPC « Custom / From-Scratch » **(Sockets + JSON-RPC)** | ✅ | Sockets TCP (`rpc_core/transport.py`, trame préfixée par 4 octets de longueur) + messages **JSON-RPC 2.0** (`rpc_core/protocol.py`). Tests : `tests/test_jsonrpc.py` (17 tests, dont les exemples de la section 7 de la spécification JSON-RPC 2.0) |
| 2b. gRPC (Protobuf) : contrat strict (IDL), sérialisation binaire | ✅ | `protos/inventory.proto`, code généré `protos/inventory_pb2*.py`, `grpc_impl/`. Tests : `tests/test_grpc.py` (30 tests) |
| 3. Mettre en valeur graphiquement et expérimentalement avantages et inconvénients (banc d'essai + tableau de bord de simulation de pannes) | ✅ | Banc d'essai `benchmark/` + `lab/benchmark.py` ; pannes `failure_simulator/` + `lab/failures.py` ; tableau de bord web `python main.py --dashboard` (vues *Mesure* et *Pannes*) |

## 2. Idée globale : « RPC Explorer & Benchmark Lab »

| Exigence | État | Où / comment |
|---|---|---|
| Service de Calcul & Gestion d'Inventaire Distribué | ✅ | `business/inventory_service.py` — logique pure, sans réseau. Tests : `tests/test_business.py` (50 tests) |
| Serveur RPC exposant `calculate_factorial`, `get_product_details`, `update_stock`, `stream_analytics` | ✅ | Les 4 méthodes sont exposées par les trois serveurs : Custom RPC (`lab/servers.py` → `RPCServer.register_service`), gRPC (`grpc_impl/grpc_server.py`), REST (`rest/rest_server.py`) |
| Client RPC / CLI & Dashboard interactif | ✅ | `python main.py` (menu, `cli/cli_runner.py`) et `python main.py --dashboard` (`dashboard/`) |
| — Lancer des appels RPC **synchrones** | ✅ | Menu entrée 1, vue *Appel*, `python main.py --call custom calculate_factorial n=5` |
| — Lancer des appels RPC **asynchrones** | ✅ | Custom RPC : `client.call_async(...)` renvoie un *future* ; gRPC : `client.calculate_factorial_async(n)` utilise `stub.CalculateFactorial.future(...)`. Démonstration : `python main.py --async-demo` (menu entrée 11, carte « Appels synchrones ou asynchrones » de la vue *Mesure*) : 5 appels de 100 ms ≈ 500 ms en synchrone, ≈ 100 ms en asynchrone. Tests : `tests/test_async_and_typing.py` |
| — Lancer des appels RPC en **streaming** | ✅ | gRPC *server streaming* (`StreamAnalytics`) ; Custom RPC : extension `rpc.stream` (`client.stream(...)`). `python main.py --streaming-demo`, vue *Flux*. Tests : `tests/test_custom_streaming.py`, `tests/test_grpc.py::...stream_analytics...` |
| — Mode « Sous le capot » : inspecter les messages JSON/Protobuf transitant sur le réseau | ✅ | `python main.py --under-the-hood` : message JSON-RPC exact et sa taille, octets Protobuf décodés champ par champ (`under_the_hood/protobuf_inspector.py`), requête HTTP brute. Option `--trace` en mode client/serveur séparés. Tests : `tests/test_under_the_hood.py`, `tests/test_protobuf_inspector.py` |
| — Banc de test comparatif : taille du payload, latence local vs distant, sérialisation JSON vs Protobuf vs REST | ✅ | `python main.py --benchmark` : latences Local / Custom RPC (connexion par appel et persistante) / gRPC / REST, octets par protocole, coût CPU de la sérialisation JSON vs Protobuf. Tests : `tests/test_benchmark.py` |
| — Simuler les failles : spikes de latence, panne réseau, incompatibilité de signature/contrat | ✅ | `python main.py --simulate-failures` (latence, timeout, serveur éteint, retry) et `python main.py --contract-demo` (client v1 / serveur v2). Tests : `tests/test_failure_scenarios.py`, `tests/test_contract_and_demos.py` |

## 3. Plan d'implémentation

### Phase 1 — Middleware Custom RPC (Under the Hood)

| Fichier demandé | État | Fichier réel |
|---|---|---|
| `rpc_core/serializer.py` : encodeur/décodeur de requêtes (ID, méthode, arguments, résultat) | ✅ | `rpc_core/serializer.py` (façade) + `rpc_core/protocol.py` (format JSON-RPC 2.0 : `id`, `method`, `params`, `result`/`error`) |
| `rpc_core/client_stub.py` : stub générant dynamiquement des appels de fonctions locales et les envoyant sur la socket | ✅ | `rpc_core/client_stub.py` : `client.update_stock(item_id=..., quantity_delta=...)` est intercepté par `__getattr__`, sérialisé et envoyé sur la socket |
| `rpc_core/server_skeleton.py` : squelette (dispatcher) réceptionnant, exécutant, renvoyant | ✅ | `rpc_core/server_skeleton.py` : table blanche des méthodes, vérification de la signature (-32602), exécution, réponse ou erreur JSON-RPC |

Exemple de message réellement envoyé (`python main.py --under-the-hood --method update_stock`) :

```text
{"jsonrpc":"2.0","method":"update_stock","params":{"item_id":"PROD-001","quantity_delta":-1},"id":"9f1c…"}
{"jsonrpc":"2.0","result":{"item_id":"PROD-001","previous_stock":42,"delta":-1,"new_stock":41,...},"id":"9f1c…"}
```

### Phase 2 — Service métier & gRPC (RPC moderne avec IDL)

| Exigence | État | Fichier réel |
|---|---|---|
| `protos/inventory.proto` : contrat IDL Protobuf | ✅ | `protos/inventory.proto` (même nom que dans l'énoncé) |
| Compilateur `protoc` pour générer les stubs | ✅ | `python scripts/generate_protos.py` (appelle `protoc` via `grpcio-tools`) → `protos/inventory_pb2.py`, `protos/inventory_pb2_grpc.py`. La CI vérifie que le code généré correspond au `.proto` |
| Serveur gRPC (`grpc_server.py`) et client (`grpc_client.py`) | ✅ | `grpc_impl/grpc_server.py`, `grpc_impl/grpc_client.py` |

### Phase 3 — Banc d'essai & démos

**Avantages du RPC**

| Exigence | État | Commande / fichier |
|---|---|---|
| 1. Transparence de localisation : `client.update_stock(item_id, qty)` vs requête HTTP REST | ✅ | `python main.py --transparency-demo` (`lab/transparency.py`) : le même `update_stock` écrit en local, Custom RPC, gRPC et REST (`requests.post(".../api/products/PROD-001/stock", json=...)`), exécuté et chronométré |
| 2. Performance & **typage strict** (gRPC vs REST) | ✅ | Typage : `python main.py --typing-demo` (`lab/typing_demo.py`) — un `n="abc"` est refusé par le stub gRPC **avant tout envoi (0 octet)**, alors qu'en JSON-RPC et en REST la requête part et le serveur répond par une erreur (-32000 / -32602, HTTP 400). Tests : `tests/test_async_and_typing.py` |
| — Taille des données sérialisées (Protobuf binaire vs JSON) | ✅ | `python main.py --benchmark`, tableau « Taille des messages sérialisés » |
| — Temps d'exécution sur 1 000 requêtes | ✅ | `python main.py --benchmark --iterations 1000` (1 000 est la valeur par défaut ; échauffement de 100 appels) |

**Inconvénients / limites du RPC**

| Exigence | État | Commande / fichier |
|---|---|---|
| 1. Simulation d'un délai réseau (ex : 200 ms) et coupure de connexion | ✅ | `python main.py --simulate-failures` : latence de 0, 50 et **200 ms**, serveur bloqué, serveur éteint (`lab/failures.py`, `failure_simulator/`) |
| — Gestion obligatoire de `Timeout`, `NetworkError`, `Retry` | ✅ | Le client lève `TimeoutError` / `ConnectionError` (gRPC : `DEADLINE_EXCEEDED` / `UNAVAILABLE`, REST : 504 / 503) ; `rpc_core/resilience.py` : `call_with_retry` (tentatives, backoff exponentiel), plus la démonstration du double décrément quand on réessaie une opération non idempotente et sa correction par clé d'idempotence. Tests : `tests/test_failure_scenarios.py`, `tests/test_resilience.py` |
| 2. Couplage fort / évolution de contrat : signature modifiée côté serveur, client IDL non mis à jour → crash/rejet | ✅ | `python main.py --contract-demo` : serveur v2 (`contract_evolution/protos_v2/inventory.proto`, processus séparé) face au client v1. Observé : rejets (`UNIMPLEMENTED`, `METHOD_NOT_FOUND`, `INVALID_ARGS`) et un **bug silencieux** (champ renuméroté : « succès » sans effet). Tests : `tests/test_contract_and_demos.py` |

### Phase 4 — Interface CLI / Dashboard

| Exigence | État | Fichier réel |
|---|---|---|
| `cli_runner.py` : menu interactif en console pour exécuter les tests, afficher les métriques, voir les messages réseau bruts en temps réel | ✅ | `cli/cli_runner.py` (menu à 12 entrées, mode « Sous le capot » activable, injection de panne) ; `python main.py` |
| (Rich/Textual **ou script simple**) | ⚠️ | Script simple : affichage en texte par `cli/ui.py`, sans dépendance. Pour la partie graphique, un tableau de bord web a été préféré à Textual (➕ ci-dessous) |
| ➕ Tableau de bord web | ➕ | `python main.py --dashboard` : vues Appel, Flux, Mesure, Pannes, Contrat ; aucun accès Internet nécessaire |

## 4. Structure des fichiers proposée → structure réelle

L'énoncé propose une structure ; le projet garde ses noms de dossiers (déjà utilisés par les tests, la CI et la documentation) mais **chaque fichier proposé a son équivalent** :

| Structure proposée | Structure réelle | Remarque |
|---|---|---|
| `implementation_plan.md` | `implementation_plan.md` | ce fichier |
| `requirements.txt` (grpcio, grpcio-tools, json-rpc, rich, tabulate) | `requirements.txt` (grpcio, grpcio-tools, protobuf, flask, requests, pytest) | ⚠️ voir « Bibliothèques » ci-dessous |
| `rpc_custom/` | `rpc_core/` | nom imposé par l'énoncé lui-même en Phase 1 (`rpc_core/serializer.py`…) |
| `rpc_custom/protocol.py` (format des messages, JSON-RPC 2.0 spec) | `rpc_core/protocol.py` | ✅ même rôle, même nom |
| `rpc_custom/client_stub.py` | `rpc_core/client_stub.py` | ✅ |
| `rpc_custom/server_skeleton.py` | `rpc_core/server_skeleton.py` | ✅ |
| `rpc_custom/custom_rpc_demo.py` | `lab/transparency.py`, `under_the_hood/explorer.py` | démos `--transparency-demo` et `--under-the-hood` |
| — | `rpc_core/serializer.py`, `rpc_core/transport.py`, `rpc_core/resilience.py` | ➕ découpage plus fin (sérialisation, trame TCP, retry) |
| `rpc_grpc/protos/service.proto` | `protos/inventory.proto` | nom imposé par l'énoncé en Phase 2 |
| `rpc_grpc/generated/` | `protos/inventory_pb2.py`, `protos/inventory_pb2_grpc.py` | générés par `scripts/generate_protos.py` |
| `rpc_grpc/grpc_server.py`, `grpc_client.py` | `grpc_impl/grpc_server.py`, `grpc_impl/grpc_client.py` | le dossier ne s'appelle pas `grpc/` pour ne pas masquer la bibliothèque `grpc` |
| `benchmark_lab/benchmark_perf.py` | `benchmark/` (moteur, adaptateurs, métriques) + `lab/benchmark.py` (démo) | |
| `benchmark_lab/failure_simulation.py` | `failure_simulator/` (latence, timeout, panne, message corrompu) + `lab/failures.py` (démo) + `contract_evolution/` (breaking changes) | |
| `main.py` | `main.py` | ✅ |
| — | `business/`, `rest/`, `under_the_hood/`, `cli/`, `dashboard/`, `tests/`, `docs/` | ➕ |

### Bibliothèques suggérées mais non utilisées

- **json-rpc** : non utilisée **volontairement**. L'objectif de la Phase 1 est d'écrire soi-même le middleware pour en comprendre les rouages ; une bibliothèque JSON-RPC cacherait justement le stub, le marshalling et le dispatcher. Le format JSON-RPC 2.0 est donc implémenté à la main dans `rpc_core/protocol.py` et vérifié par `tests/test_jsonrpc.py` sur les exemples officiels de la spécification.
- **rich / tabulate** : remplacées par `cli/ui.py` (une centaine de lignes, tableaux et titres en texte), pour garder le projet installable sans dépendance d'affichage. L'énoncé autorise un « script simple ».
- **flask / requests** (ajoutées) : nécessaires au point de comparaison REST demandé par l'énoncé (« gRPC vs REST »).

## 5. Plan de vérification & démonstration

| Vérification demandée | Commande | Test automatique |
|---|---|---|
| Lancement du serveur Custom RPC et exécution des appels distants via le stub | `python main.py --serve custom --trace` puis, dans un 2e terminal, `python main.py --call custom calculate_factorial n=5 --trace` | `tests/test_custom_rpc.py`, `tests/test_jsonrpc.py` |
| Lancement du serveur gRPC et test des appels unaires et streaming | `python main.py --serve grpc` puis `python main.py --call grpc calculate_factorial n=5` et `python main.py --call grpc stream_analytics metric_name=cpu_usage count=5` | `tests/test_grpc.py` |
| `python main.py --benchmark` : taille du paquet (octets) JSON vs Protobuf, temps moyen par appel Local vs Custom RPC vs gRPC | `python main.py --benchmark` (REST est mesuré en plus) | `tests/test_benchmark.py` |
| `python main.py --simulate-failures` : appel local vs appel RPC soumis aux règles du réseau | `python main.py --simulate-failures` | `tests/test_failure_scenarios.py`, `tests/test_contract_and_demos.py` |

> L'énoncé écrit `-benchmark` et `-simulate-failures` : c'est le rendu typographique de `--benchmark` / `--simulate-failures` (deux tirets), qui sont les options réelles.

Tout enchaîner dans l'ordre de la soutenance : `python main.py --demo`.

---

## 6. Ce qui a été ajouté pour coller à l'énoncé (version 1.4.0)

| Écart constaté | Correction |
|---|---|
| Les messages Custom RPC étaient en JSON « maison » (`id`, `method`, `args`, `metadata`), pas en JSON-RPC | Format **JSON-RPC 2.0** complet : `rpc_core/protocol.py`, codes d'erreur standard, notifications, lots ; streaming reformulé en extension `rpc.stream` |
| Les appels asynchrones existaient (`call_async`) mais n'étaient ni démontrés ni disponibles côté gRPC | `calculate_factorial_async` (gRPC `.future()`), `--async-demo`, entrée 11 du menu, carte dans le tableau de bord, tests |
| Le typage strict de gRPC était affirmé sans être démontré | `--typing-demo`, entrée 12 du menu, carte dans la vue *Contrat*, tests |
| Pas de `implementation_plan.md` | ce fichier |
