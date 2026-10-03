# Phase 08 — Synthèse du benchmark comparatif réel

**Date d'exécution :** 3 octobre 2026 (UTC)
**Statut des chiffres :** VÉRIFIÉ. Toutes les valeurs ci-dessous sont recopiées depuis
`docs/benchmark/phase08_raw_results.json` (campagne principale) et
`docs/benchmark/phase08_raw_results_in_process.json` (variante), produits par
`benchmark/run_comparative_benchmark.py`. Aucune valeur n'a été saisie ou retouchée à la main.

Commande de reproduction (depuis la racine du dépôt) :

```bash
python -m benchmark.run_comparative_benchmark                 # campagne principale
python -m benchmark.run_comparative_benchmark --in-process \
    --output docs/benchmark/phase08_raw_results_in_process.json  # variante même processus
```

---

## 1. Conditions expérimentales

| Paramètre | Valeur |
|---|---|
| OS | Linux 6.18.44 (conteneur cloud), x86_64 |
| CPU | Intel Xeon @ 2.10 GHz, 4 CPU logiques |
| RAM | 16 094 Mo |
| Python | 3.11.15 |
| Bibliothèques | grpcio 1.84.0, protobuf 7.36.2, Flask 3.1.3, Werkzeug 3.1.9, requests 2.34.2 |
| Réseau | loopback `127.0.0.1`, même machine |
| Placement (principal) | un processus Python dédié par serveur, client dans un autre processus |
| Latence séquentielle | 3 répétitions × 2 000 appels mesurés, 200 appels de chauffe avant chaque série, ordre des protocoles permuté à chaque répétition |
| Concurrence | 1, 4, 8, 16 threads, 250 appels mesurés par thread, un client par thread, opération `calculate_factorial(5)` |
| Octets sur le fil | proxy TCP de comptage, 200 appels mesurés après un premier appel compté à part |
| Latence artificielle / simulateur de pannes | désactivés (0 ms) |
| Log par requête de Werkzeug | coupé (niveau ERROR) pour ne pas mesurer l'écriture console |

Paramètres d'appel identiques pour tous les protocoles : `calculate_factorial(n=5)`,
`get_product_details("PROD-001")`, `update_stock("PROD-002", +1)`, `stream_analytics("cpu_usage", 5)`.

### Définitions

- **Latence** : durée côté client (`time.perf_counter`) entre l'appel de l'adaptateur et le retour du résultat désérialisé, en ms.
- **p50 / p95 / p99** : percentiles par interpolation linéaire (`benchmark/metrics.py`).
- **Débit** : appels réussis ÷ durée totale de la série (req/s).
- **Taux d'erreur** : appels en échec ÷ appels tentés.
- **Octets sur le fil** : charge utile TCP dans chaque sens (framing, en-têtes HTTP, trames HTTP/2 inclus ; en-têtes TCP/IP exclus).

### Différences de conditions à garder en tête (règle de comparabilité)

1. **Connexions TCP.** Mesuré par le proxy : le client Custom RPC ouvre **une connexion TCP par appel**
   (`rpc_core/client_stub.py`), et le serveur Werkzeug renvoie `Connection: close`, donc REST ouvre aussi
   **une connexion par appel** malgré la `requests.Session`. gRPC réutilise **un seul canal HTTP/2**
   (0 nouvelle connexion sur 200 appels).
2. **`stream_analytics`.** gRPC utilise un vrai *server streaming* (5 messages Protobuf) ; Custom RPC et
   REST renvoient une liste JSON en une seule réponse. Le travail métier est le même, le mode de
   transmission ne l'est pas.
3. **Serveurs.** Custom RPC : un thread par connexion. gRPC : `ThreadPoolExecutor(max_workers=10)`.
   REST : serveur de développement Werkzeug, multi-threadé. Aucun n'est un serveur de production.

---

## 2. Latence séquentielle (1 client, serveurs en processus séparés)

18 000 appels par protocole et par opération au total (3 × 2 000 mesurés par opération), **0 erreur**
sur l'ensemble de la campagne (taux d'erreur 0,0 % partout).

Latences en ms, statistiques calculées sur les 6 000 appels poolés des 3 répétitions.

#### `calculate_factorial(5)`

| Protocole | Moyenne | p50 | p95 | p99 | Max | Écart-type | Débit (req/s) |
|---|---|---|---|---|---|---|---|
| Local (référence) | 0.001 | 0.001 | 0.001 | 0.001 | 0.035 | 0.001 | 1 430 258 |
| Custom RPC | 0.476 | **0.424** | 0.767 | 1.245 | 6.167 | 0.251 | **2 098** |
| gRPC | 0.723 | 0.674 | 1.122 | 1.619 | 6.729 | 0.284 | 1 382 |
| REST | 1.948 | 1.856 | 2.489 | 3.654 | 33.401 | 0.663 | 513 |

#### `get_product_details("PROD-001")`

| Protocole | Moyenne | p50 | p95 | p99 | Max | Écart-type | Débit (req/s) |
|---|---|---|---|---|---|---|---|
| Local (référence) | 0.003 | 0.002 | 0.006 | 0.010 | 0.196 | 0.004 | 330 575 |
| Custom RPC | 0.452 | **0.416** | 0.688 | 0.934 | 5.007 | 0.198 | **2 208** |
| gRPC | 0.771 | 0.718 | 1.162 | 1.553 | 35.955 | 0.625 | 1 295 |
| REST | 1.827 | 1.758 | 2.326 | 3.297 | 8.477 | 0.385 | 547 |

#### `update_stock("PROD-002", +1)`

| Protocole | Moyenne | p50 | p95 | p99 | Max | Écart-type | Débit (req/s) |
|---|---|---|---|---|---|---|---|
| Local (référence) | 0.002 | 0.002 | 0.003 | 0.005 | 0.124 | 0.002 | 430 230 |
| Custom RPC | 0.468 | **0.427** | 0.758 | 1.016 | 4.495 | 0.188 | **2 133** |
| gRPC | 0.763 | 0.718 | 1.196 | 1.588 | 5.700 | 0.266 | 1 309 |
| REST | 1.935 | 1.853 | 2.476 | 3.574 | 10.441 | 0.428 | 516 |

#### `stream_analytics("cpu_usage", 5)`

| Protocole | Moyenne | p50 | p95 | p99 | Max | Écart-type | Débit (req/s) |
|---|---|---|---|---|---|---|---|
| Local (référence) | 0.009 | 0.008 | 0.011 | 0.027 | 0.214 | 0.004 | 110 430 |
| Custom RPC (liste JSON) | 0.551 | **0.522** | 0.782 | 1.016 | 8.107 | 0.242 | **1 810** |
| gRPC (server streaming) | 1.738 | 1.663 | 2.232 | 3.232 | 11.158 | 0.431 | 575 |
| REST (liste JSON) | 1.871 | 1.820 | 2.275 | 2.973 | 11.109 | 0.342 | 534 |

**Stabilité entre répétitions (p50, ms).** Exemple `calculate_factorial` : Custom RPC 0.485 / 0.379 / 0.432,
gRPC 0.684 / 0.694 / 0.643, REST 1.860 / 1.903 / 1.802. Le classement est identique dans chaque
répétition et pour chaque opération (détail complet dans `latency.per_repetition` du JSON).

---

## 3. Débit sous charge concurrente (`calculate_factorial`, serveurs en processus séparés)

| Protocole | Threads | Appels | Erreurs | Débit (req/s) | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|---|
| Custom RPC | 1 | 250 | 0 | 2 098 | 0.419 | 0.771 | 1.060 |
| Custom RPC | 4 | 1 000 | 0 | **2 804** | 1.344 | 1.961 | 3.446 |
| Custom RPC | 8 | 2 000 | 0 | 2 375 | 3.142 | 5.044 | 6.383 |
| Custom RPC | 16 | 4 000 | 0 | 2 771 | 5.549 | 7.756 | 8.741 |
| gRPC | 1 | 250 | 0 | 1 483 | 0.623 | 1.009 | 1.154 |
| gRPC | 4 | 1 000 | 0 | 2 052 | 1.821 | 2.975 | 3.989 |
| gRPC | 8 | 2 000 | 0 | 1 905 | 3.910 | 6.263 | 9.739 |
| gRPC | 16 | 4 000 | 0 | **2 063** | 7.462 | 10.943 | 13.194 |
| REST | 1 | 250 | 0 | 475 | 2.027 | 3.145 | 3.779 |
| REST | 4 | 1 000 | 0 | 727 | 5.215 | 8.602 | 10.285 |
| REST | 8 | 2 000 | 0 | 760 | 10.015 | 16.091 | 20.401 |
| REST | 16 | 4 000 | 0 | **774** | 19.852 | 30.161 | 37.735 |

0 erreur à tous les niveaux. Au-delà de 4 threads, le débit ne progresse plus nettement pour aucun
des trois protocoles, tandis que la latence par appel augmente à peu près proportionnellement au
nombre de threads.

---

## 4. Octets réellement transmis sur le fil (par appel, régime établi)

| Opération | Protocole | Requête (o) | Réponse (o) | Total (o) | Connexions TCP / 200 appels |
|---|---|---|---|---|---|
| calculate_factorial | Custom RPC | 164 | 164 | 328 | 200 |
| | gRPC | 60.4 | 75.3 | **135.7** | 0 |
| | REST | 219 | 260.5 | 479.5 | 200 |
| get_product_details | Custom RPC | 179 | 340 | 519 | 200 |
| | gRPC | 68.4 | 138.3 | **206.8** | 0 |
| | REST | 167 | 366 | 533 | 200 |
| update_stock | Custom RPC | 193 | 288 | 481 | 200 |
| | gRPC | 70.4 | 184.3 | **254.7** | 0 |
| | REST | 247 | 318 | 565 | 200 |
| stream_analytics | Custom RPC | 198 | 745 | 943 | 200 |
| | gRPC | 62.0 | 337.3 | **399.3** | 0 |
| | REST | 177 | 777 | 954 | 200 |

Premier appel gRPC (ouverture du canal : préface HTTP/2, SETTINGS, en-têtes complets) :
432 o envoyés / 253 o reçus pour `calculate_factorial`, contre 60 / 75 o ensuite.
Les valeurs gRPC non entières sont des moyennes (trames de contrôle HTTP/2 occasionnelles).

Ces chiffres complètent la mesure existante `run_payload_size_comparison()` qui ne compte que le
message sérialisé seul (ex. `calculate_factorial` : Protobuf 13 o, JSON REST 58 o, enveloppe JSON
Custom RPC 280 o) : sur le fil, les en-têtes HTTP et le framing pèsent davantage que le corps.

**Micro-benchmark de sérialisation** (10 000 itérations, objet produit) : JSON 2.280 µs encodage +
1.711 µs décodage = 3.991 µs ; Protobuf 0.174 + 0.202 = 0.375 µs.

---

## 5. Variante : serveurs dans le même processus que le client

Même script avec `--in-process` (montage identique à `tests/test_benchmark.py`). Le classement
séquentiel reste le même (p50 `calculate_factorial` : Custom RPC 0.520 ms, gRPC 0.711 ms,
REST 2.323 ms), mais le débit sous charge s'effondre :

| Protocole | Débit max, processus séparés | Débit max, même processus |
|---|---|---|
| Custom RPC | 2 804 req/s (4 threads) | 1 936 req/s (1 thread) |
| gRPC | 2 063 req/s (16 threads) | 1 680 req/s (4 threads) |
| REST | 774 req/s (16 threads) | 421 req/s (1 thread) |

---

## 6. Interprétation

**FAITS / MESURES**

- 0 erreur sur toutes les campagnes (latence, concurrence, octets), dans les deux placements.
- Appel local : p50 de 0.6 µs pour `calculate_factorial` (valeur JSON 0.0006 ms) contre 0.424 ms
  (Custom RPC), 0.674 ms (gRPC) et 1.856 ms (REST), soit un rapport d'environ 700, 1 100 et 3 100.
  Pour `get_product_details` (local 2 µs), le rapport est d'environ 210, 360 et 880.
- En séquentiel, sur les 4 opérations, l'ordre des p50 est Custom RPC < gRPC < REST, sauf
  `stream_analytics` où gRPC (1.663 ms) et REST (1.820 ms) sont proches.
- gRPC transmet 1,9 à 3,5 fois moins d'octets par appel que Custom RPC et REST, et n'ouvre aucune
  nouvelle connexion TCP en régime établi.
- Sous charge, Custom RPC atteint le débit maximal mesuré (2 804 req/s), REST le plus faible (774 req/s).

**OBSERVATIONS**

- Dans cette configuration (loopback, Python, un seul client), le RPC maison minimal est plus rapide
  que gRPC malgré une connexion TCP par appel et des messages plus gros : la compacité de Protobuf ne
  se traduit pas en latence sur loopback.
- Le server streaming gRPC coûte environ 1 ms de plus que l'unaire gRPC pour un travail métier
  similaire (p50 1.663 vs 0.674 à 0.718 ms).
- Ces résultats **diffèrent** du rapport de phase 06 (Windows, même processus, 500 itérations), où
  gRPC devançait Custom RPC. Les deux machines et OS diffèrent : les chiffres ne sont pas comparables
  entre eux.

**HYPOTHÈSES (non vérifiées)**

- Sur loopback Linux, l'ouverture d'une connexion TCP est bon marché ; le coût d'empilement de la pile
  gRPC Python (C-core, HTTP/2, threads de complétion) peut dépasser ce coût. Sur un vrai réseau avec
  un RTT de plusieurs ms, la connexion par appel de Custom RPC et REST (1 RTT de plus pour le
  *handshake*) devrait inverser l'avantage au profit de gRPC. À vérifier avec la latence artificielle
  de la phase 07.
- Le surcoût du streaming gRPC proviendrait de la gestion par message côté Python (itérateur serveur,
  une trame par message). Non profilé.
- L'effondrement en « même processus » s'expliquerait par le GIL partagé entre threads clients et
  threads serveurs.

**Limites.** Machine virtuelle partagée (bruit possible, visible sur les `max`), un seul hôte, serveurs
de démonstration et non de production, client et serveur en Python. Les conclusions valent pour ces
conditions uniquement ; elles ne disent pas qu'un protocole est « toujours » plus rapide qu'un autre.
