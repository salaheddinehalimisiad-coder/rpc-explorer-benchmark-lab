# Guide pour comprendre le projet (à lire en premier)

Ce guide explique, sans prérequis, **de quoi parle le projet**, **comment il est construit** et **comment le présenter**. Chaque notion renvoie à une commande que vous pouvez lancer pour la voir de vos propres yeux.

---

## 1. Le problème de départ

Dans un programme normal, appeler une fonction est trivial :

```python
stock = service.update_stock("PROD-001", -1)
```

La fonction est dans le même programme, sur la même machine, en mémoire. Ça prend environ **1 microseconde** et ça ne peut pas « tomber en panne réseau ».

Maintenant imaginez que `service` tourne sur **un autre ordinateur** (un serveur d'inventaire central, par exemple). Comment appeler `update_stock` là-bas ? Il faut :

1. transformer le nom de la fonction et ses arguments en **octets** (on appelle ça *sérialiser* ou *marshaller*) ;
2. envoyer ces octets sur le **réseau** ;
3. côté serveur, recevoir les octets, les **désérialiser**, retrouver la bonne fonction, l'exécuter ;
4. renvoyer le résultat par le même chemin, en sens inverse.

Le **RPC (Remote Procedure Call, appel de procédure distante)** est l'idée de cacher tout cela derrière un objet qui *ressemble* à un appel local :

```python
client.update_stock(item_id="PROD-001", quantity_delta=-1)   # mais exécuté sur une autre machine !
```

C'est le premier concept de **middleware** (logiciel « du milieu », entre l'application et le réseau).

---

## 2. Les pièces d'un RPC (vocabulaire à connaître)

```
CÔTÉ CLIENT                                         CÔTÉ SERVEUR
───────────                                         ────────────
code appelant
   │ client.update_stock(...)
   ▼
STUB (souche client) ── fabrique le message
   │
   ▼
SÉRIALISATION ── message → octets (JSON, Protobuf…)
   │
   ▼
TRANSPORT ───────────── réseau (TCP, HTTP…) ─────────▶ réception des octets
                                                         │
                                                         ▼
                                                    DÉSÉRIALISATION
                                                         │
                                                         ▼
                                                    SKELETON / DISPATCHER
                                                    « quelle fonction ? est-elle autorisée ? »
                                                         │
                                                         ▼
                                                    FONCTION MÉTIER (la vraie)
                                                         │
◀──────────────── réponse sérialisée ◀──────────────────┘
```

| Terme | Rôle | Fichier dans le projet |
|---|---|---|
| **Stub** | objet côté client qui imite la fonction distante | `rpc_core/client_stub.py` |
| **Sérialisation** | objet Python ⇄ octets | `rpc_core/serializer.py` (JSON) |
| **Transport** | envoyer/recevoir des octets sur le réseau | `rpc_core/transport.py` (TCP) |
| **Skeleton / Dispatcher** | côté serveur : décoder, trouver la fonction, l'exécuter | `rpc_core/server_skeleton.py` |
| **Table blanche** | liste des fonctions autorisées (sécurité : on n'exécute jamais n'importe quel nom reçu du réseau) | `RPCServer.register_method` |
| **IDL / contrat** | description formelle des fonctions et messages, partagée par client et serveur | `protos/inventory.proto` |

▶ **À lancer :** `python main.py --under-the-hood` — vous verrez chacune de ces étapes s'afficher avec l'heure précise, les octets envoyés et leur taille.

---

## 3. Les trois façons de faire comparées dans le projet

### 3.1 Custom RPC (« fait maison »)
Nous avons écrit le middleware nous-mêmes, pour le **comprendre**. Les messages suivent la norme **JSON-RPC 2.0** (fichier `rpc_core/protocol.py`) et sont envoyés sur une socket TCP :

```text
requête  {"jsonrpc": "2.0", "method": "update_stock", "params": {"item_id": "PROD-001", "quantity_delta": -1}, "id": "9f1c…"}
réponse  {"jsonrpc": "2.0", "result": {"item_id": "PROD-001", "previous_stock": 42, "new_stock": 41, ...}, "id": "9f1c…"}
erreur   {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Méthode inconnue …", "data": {"name": "METHOD_NOT_FOUND"}}, "id": "9f1c…"}
```

L'`id` relie la réponse à sa requête. Les codes d'erreur sont ceux de la spécification (-32700 JSON illisible, -32600 requête invalide, -32601 méthode inconnue, -32602 paramètres invalides, -32603 erreur interne) plus -32000 quand la fonction métier lève une exception. La norme prévoit aussi les **notifications** (requête sans `id` : pas de réponse) et les **lots** (un tableau de requêtes envoyé d'un coup) : `client.notify(...)` et `client.batch([...])`. Comme TCP est un flux continu d'octets (il ne connaît pas la notion de « message »), chaque message est précédé de **4 octets donnant sa longueur** : c'est le *framing*.

### 3.2 gRPC (RPC industriel de Google)
- On écrit d'abord un **contrat** dans un fichier `.proto` (le langage IDL de Protobuf).
- Le compilateur `protoc` **génère** automatiquement le stub client et la base du serveur (`protos/inventory_pb2*.py`).
- Les messages sont encodés en **Protobuf binaire** : très compact. Par exemple `FactorialRequest(n=5)` fait **2 octets** : `08 05` (= « champ n°1, entier, valeur 5 »). Les **noms** des champs ne voyagent jamais, seulement leurs **numéros**.
- Transport : HTTP/2. gRPC sait faire du **streaming** (`StreamAnalytics` : une requête → plusieurs réponses).

### 3.3 REST (la référence du web)
Ce n'est pas du RPC : on manipule des **ressources** (`/api/products/PROD-001`) avec des verbes HTTP (`GET`, `POST`). Le client doit construire lui-même URL, corps JSON, et interpréter les codes HTTP (200, 404, 503…). Sert ici de **point de comparaison**.

▶ **À lancer :** `python main.py --transparency-demo` — le même besoin codé des 4 façons, exécuté et chronométré.

---

## 4. Les avantages du RPC (ce que la démo doit montrer)

1. **Transparence de localisation** : le code client ressemble à un appel local (`client.update_stock(...)`), le réseau est caché par le stub.
2. **Contrat et typage strict (gRPC)** : le `.proto` impose les types ; le code client/serveur est généré, donc cohérent. Démonstration : `python main.py --typing-demo`.
3. **Performance (gRPC)** : messages binaires beaucoup plus petits que du JSON, sérialisation plus rapide.
4. **Appels asynchrones** : le client n'est pas obligé d'attendre chaque réponse. Démonstration : `python main.py --async-demo`.

▶ `python main.py --benchmark` — tailles en octets et coût de sérialisation JSON vs Protobuf, latences de chaque protocole.

## 5. Les inconvénients / pièges du RPC

1. **Le piège de la transparence** : un appel distant *ressemble* à un appel local mais n'en est pas un. Il est des dizaines à des milliers de fois plus lent, subit la latence du réseau, et peut **échouer** (timeout, serveur éteint). Le code appelant **doit** gérer `Timeout`, `ConnectionError`, et éventuellement réessayer (*retry*).
2. **Le retry n'est pas gratuit** : si la première requête a été exécutée mais que la réponse s'est perdue, réessayer `update_stock` retire le stock **deux fois**. Solution : une **clé d'idempotence**.
3. **Couplage fort / évolution du contrat** : si le serveur change la signature d'une fonction sans que les clients soient mis à jour, ça casse — parfois avec une erreur claire, parfois **silencieusement** (mauvaises données sans aucune erreur).

▶ `python main.py --simulate-failures` puis `python main.py --contract-demo`.

---

## 6. Ce que montre la démo d'évolution de contrat (résumé)

| Changement côté serveur v2 | Custom RPC (JSON, par **nom**) | gRPC (Protobuf, par **numéro**) |
|---|---|---|
| Ajouter un champ / paramètre optionnel | compatible | compatible (champ inconnu ignoré) |
| Renommer un champ | **casse** (INVALID_ARGS) | compatible (le numéro n'a pas changé) |
| Renuméroter un champ | — | **bug silencieux** : « succès » mais le stock n'a pas bougé |
| Changer le type d'un champ | — | erreur avec un message **trompeur** |
| Renommer une méthode | **casse** (METHOD_NOT_FOUND) | **casse** (UNIMPLEMENTED) |

Règle d'or Protobuf : on ne change **jamais** le numéro ni le type d'un champ existant ; on en ajoute de nouveaux, on marque les anciens `reserved`, et pour un vrai changement cassant on crée un nouveau package (`inventory.v2`).

---

## 7. Comment sont organisés les fichiers

- `business/` — la logique métier **pure** (factorielle, stock…). Elle ne sait pas qu'il existe un réseau : c'est voulu, les trois protocoles l'exposent sans la modifier.
- `rpc_core/`, `grpc_impl/`, `rest/` — les trois middlewares.
- `under_the_hood/` — l'observation (traces, décodage Protobuf).
- `benchmark/`, `failure_simulator/`, `contract_evolution/`, `lab/` — les expériences.
- `cli/` + `main.py` — l'interface.
- `tests/` — 269 tests automatiques (`python -m pytest -q`).

---

## 8. Scénario de présentation conseillé (≈ 15 min)

Le plus visuel : `python main.py --dashboard` ouvre une page dans le navigateur qui couvre toutes les étapes ci-dessous (vues *Appel*, *Flux*, *Mesure*, *Pannes* et *Contrat*, dans le menu de gauche). Dans la vue Appel, les cartes « Par où commencer » lancent chaque démonstration en un clic, et « Comparer les 3 » exécute le même appel sur les trois protocoles. Les commandes en console restent utiles en secours.

1. **Le service** : montrer `business/inventory_service.py` (4 fonctions simples).
2. **Appel local vs RPC** : `python main.py --transparency-demo`.
3. **Sous le capot** : `python main.py --under-the-hood --method update_stock` — commenter stub → JSON → TCP → dispatcher → exécution ; puis les octets Protobuf ; puis la requête HTTP brute.
4. **Vrai réseau** (optionnel) : terminal 1 `python main.py --serve all --trace`, terminal 2 `python main.py --call custom update_stock item_id=PROD-001 quantity_delta=-2 --trace`.
5. **Streaming** : `python main.py --under-the-hood --method stream_analytics`, puis `python main.py --streaming-demo` (la 1re mesure arrive tout de suite en flux, au bout de ~1 s en réponse unique).
5b. **Synchrone / asynchrone et typage** : `python main.py --async-demo` puis `python main.py --typing-demo` (vues *Mesure* et *Contrat* du tableau de bord).
6. **Benchmark** : `python main.py --benchmark --iterations 1000` — insister : *mesures sur cette machine, en localhost*.
7. **Pannes** : `python main.py --simulate-failures` — latence, timeout, serveur éteint, retry, double décrément.
8. **Contrat** : `python main.py --contract-demo` — le bug silencieux du renumérotage.
9. **Conclusion** : RPC = simplicité de code et performance (gRPC), mais un appel distant reste un appel distant : latence, pannes, contrat à gérer.

---

## 9. Questions qu'on peut vous poser (et éléments de réponse)

- **Pourquoi un préfixe de longueur sur TCP ?** TCP transmet un flux d'octets sans frontières de messages ; sans longueur, le serveur ne sait pas où s'arrête un message.
- **Pourquoi une table blanche ?** Pour ne jamais exécuter une fonction arbitraire dont le nom vient du réseau (sécurité).
- **Pourquoi gRPC est-il compact ?** Binaire + numéros de champs au lieu des noms + entiers en *varint*.
- **Pourquoi le Custom RPC peut-il battre gRPC en localhost ?** Il fait beaucoup moins de choses (pas d'HTTP/2, pas de gestion de flux, pas de métadonnées) — c'est une **observation** dans nos conditions, pas une vérité générale.
- **Qu'est-ce que l'idempotence ?** Une opération qu'on peut répéter sans changer le résultat (lire un produit : oui ; retirer 1 du stock : non).
- **Comment marche votre streaming Custom RPC ?** JSON-RPC 2.0 ne prévoit pas de streaming : nous l'ajoutons comme extension. Le client appelle la méthode réservée `rpc.stream` ; le serveur envoie une notification `rpc.stream.item` par élément, puis une réponse normale `{"count": N}`. Chaque message reste un objet JSON-RPC 2.0 valide, précédé de sa longueur. Si le client part, l'envoi échoue et le serveur arrête de produire.
- **Pourquoi le serveur v2 tourne-t-il dans un autre processus ?** Les deux contrats déclarent les mêmes noms Protobuf ; ils ne peuvent pas coexister dans le même programme — exactement comme deux versions d'un serveur réel.
- **Un appel RPC est-il forcément bloquant ?** Non. `python main.py --async-demo` : 5 appels de 100 ms prennent ~500 ms en synchrone et ~100 ms en asynchrone (`client.call_async(...)` en Custom RPC, `stub.CalculateFactorial.future(...)` en gRPC).
- **Que veut dire « typage strict » pour gRPC ?** `python main.py --typing-demo` : avec `n="abc"`, le stub gRPC généré refuse l'appel avant d'envoyer le moindre octet ; en JSON-RPC et en REST la requête part et c'est le serveur qui doit vérifier.
