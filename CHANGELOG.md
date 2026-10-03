# Changelog

## [1.2.0] — 2026-10-03

### Modifié
- **Tableau de bord** : nouveau design « banc de mesure » (diagramme de séquence réel de chaque appel, inspecteur d'octets, vue analyseur logique pour le flux), polices embarquées, thème clair uniquement.

### Ajouté
- Points de départ guidés, comparaison du même appel sur les trois protocoles, historique des appels cliquable, bouton Copier, raccourci Ctrl + Entrée, bandeau quand une panne est active, adresse de vue dans l'URL (#flux, #mesure…), échec réseau dessiné dans la séquence.

## [1.1.0] — 2026-10-03

### Ajouté
- **Streaming Custom RPC** : `RPCServer.register_stream()` / `RPCClient.stream()` (une trame par élément + trame de fin ou d'erreur ; arrêt côté serveur si le client part) ; `InventoryService.stream_analytics_iter()` ; démo `--streaming-demo`.
- **Tableau de bord web** (`python main.py --dashboard`) : trajet d'un appel en deux couloirs client/serveur, octets Protobuf colorés par champ, requête HTTP brute, flux en direct (Server-Sent Events), benchmark en barres, injection de pannes, expériences, évolution de contrat. Page unique sans dépendance Internet, thèmes clair/sombre, utilisable sur mobile.
- 20 nouveaux tests (246 au total).

## [1.0.0] — 2026-10-03

### Corrigé
- **Masquage de la bibliothèque `grpc`** : le dossier `grpc/` du projet portait le même nom que la bibliothèque officielle grpcio et nécessitait un hack `sys.modules`. Renommé en `grpc_impl/`, hack supprimé.
- **`RPCServer.stop()`** ne coupait pas les connexions clientes déjà ouvertes et laissait le port occupé sous Linux (thread bloqué dans `accept()`). Les connexions actives sont maintenant fermées et le port libéré. Effet de bord : les 188 tests existants passent de ~13 s à ~5 s.
- **Client REST** : un dépassement de délai était signalé comme « 503 CONNECTION_ERROR » ; il est maintenant distingué (`504 TIMEOUT`).
- **Dépendances** : `requests` (utilisé) manquait ; `numpy`, `matplotlib`, `pyyaml`, `python-dotenv`, `pytest-asyncio` (inutilisés) retirés ; versions minimales alignées sur le code Protobuf généré (grpcio ≥ 1.84, protobuf ≥ 7.35.1).
- **README** : chiffres de benchmark inventés, noms de fichiers de tests et commande `protoc` erronés, feuille de route obsolète — réécrit.

### Ajouté
- **Sous le capot** : `RPCTracer` (frise des étapes client + serveur), décodeur du binaire Protobuf, intercepteur client gRPC, démo comparée Custom RPC / gRPC / REST (`--under-the-hood`).
- **Client Custom RPC** : connexion TCP persistante optionnelle, appels asynchrones (`call_async` → `Future`), context manager.
- **Résilience** : `rpc_core.resilience.call_with_retry` (retry explicite, backoff exponentiel, erreurs métier jamais réessayées).
- **Démos** : transparence de localisation, local ≠ distant (latence, timeout, serveur éteint, retry au redémarrage, piège du retry non idempotent + clé d'idempotence).
- **Évolution de contrat (Phase 10)** : contrat v2 et serveur v2 en processus séparé ; scénarios compatibles, cassants visibles et cassants silencieux, pour Custom RPC et gRPC.
- **CLI interactif (Phase 11)** et `main.py` complet : `--demo`, `--benchmark`, `--simulate-failures`, `--contract-demo`, `--transparency-demo`, `--serve`, `--call`.
- **Benchmark** : campagne complète avec Custom RPC mesuré avec et sans connexion persistante, conditions expérimentales enregistrées, export JSON.
- `scripts/generate_protos.py`, CI GitHub Actions (Linux + Windows), `docs/GUIDE_COMPRENDRE.md`.
- 38 nouveaux tests (226 au total).

## [0.7.0] — 2026-09-26
- Phases 01 à 07 : fondation, Custom RPC, service métier, gRPC, REST, moteur de benchmark, simulateur de pannes (188 tests).
