# CAHIER DES CHARGES OFFICIEL DU PFE / PROJET SOA

**Source :** Feuille de route transmise par l'encadrant M. Yacine Said (`boulahia.yacinesaid@gmail.com`) le jeu. 24 sept. 2026.  
**Photographies originales :** Archivées dans [`docs/spec_photos/`](spec_photos/)  
**Titre du Projet :** Feuille de route : Démonstrateur & Framework d'Exploration RPC (Remote Procedure Call)  
**Nom du Système :** « RPC Explorer & Benchmark Lab »  

---

## 1. Contexte & Objectif

Le **Remote Procedure Call (RPC)** est le premier concept fondamental de middleware pour les systèmes distribués. Il permet à un programme d'exécuter une procédure (fonction) sur une machine distante comme si elle était exécutée localement (transparence de localisation).

Ce projet vise à créer un démonstrateur interactif et pédagogique (**RPC-Explorer**) permettant de :

1. **Comprendre les rouages internes du RPC** :
   - Stub client
   - Marshalling / Sérialisation
   - Transport réseau
   - Squelette / Dispatcher serveur
   - Démarshalling
2. **Comparer deux approches de RPC** :
   - **RPC "Custom / From-Scratch" (Sockets + JSON-RPC)** : Pour visualiser le rôle exact du middleware (Stub & Skeleton).
   - **gRPC (Protobuf)** : Pour illustrer le RPC moderne avec contrat strict (IDL) et sérialisation binaire haute performance.
3. **Mettre en valeur graphiquement et expérimentalement les Avantages & Inconvénients du RPC** grâce à un banc d'essai/benchmark et un tableau de bord de simulation de pannes réseau.

---

## 2. Idée globale du Projet : "RPC Explorer & Benchmark Lab"

Le projet simulera un **Service de Calcul & Gestion d'Inventaire Distribué**.

Il comprendra :
- **Un Serveur RPC** exposant des méthodes métier :
  - `calculate_factorial`
  - `get_product_details`
  - `update_stock`
  - `stream_analytics`
- **Un Client RPC / CLI & Dashboard Interactif** permettant au développeur de :
  - Lancer des appels RPC (synchrones, asynchrones, streaming).
  - Activer un mode "Sous le capot" (inspecter les messages JSON/Protobuf transitant sur le réseau).
  - Lancer un banc de test comparatif (Taille du payload, Latence local vs distant, Sérialisation JSON vs Protobuf vs REST).
  - Simuler les failles du RPC (Spikes de latence, Panne réseau, Incompatibilité de signatures/contrat).

---

## 3. Plan d'Implémentation & Feuilles de Route

### Phase 1 : Architecture du Middleware Custom RPC (Under the Hood)
Création d'un mini-engine RPC en Python pour comprendre la théorie :
- `rpc_core/serializer.py` : Encodeur/Décodeur de requêtes (ID, méthode, arguments, résultat).
- `rpc_core/client_stub.py` : Stub générant dynamiquement des appels de fonctions locales et les envoyant sur la socket.
- `rpc_core/server_skeleton.py` : Squelette (Dispatcher) réceptionnant les messages, exécutant la fonction locale et renvoyant le résultat.

### Phase 2 : Service Métier & Implémentation gRPC (RPC Moderne avec IDL)
- `protos/inventory.proto` : Définition du contrat IDL (Interface Definition Language) avec Protobuf.
- Compilateur `protoc` pour générer le code client/serveur stubs.
- Implémentation du serveur gRPC Python (`grpc_server.py`) et du client (`grpc_client.py`).

### Phase 3 : Banc d'Essai & Démos Avantages / Inconvénients

#### 💡 Démonstrateur des AVANTAGES du RPC :
1. **Transparence de Localisation (Simplicité de code)** :
   - Comparaison du code client : Appel direct type `client.update_stock(item_id, qty)` vs Requête HTTP REST (`fetch('/api/stock/...', {method: 'POST', body: ...})`).
2. **Performance & Typage Strict (gRPC vs REST)** :
   - Mesure de la taille des données sérialisées (Protobuf binaire vs JSON).
   - Temps d'exécution sur 1 000 requêtes.

#### ⚠️ Démonstrateur des INCONVÉNIENTS / LIMITES du RPC :
1. **Le piège de la Transparence (Latence et Panne Réseau)** :
   - Simulation d'un délai réseau (ex: 200ms) et coupure de connexion.
   - Démonstration de pourquoi un appel RPC distant ne doit pas être traité comme une fonction locale classique (gestion obligatoire de Timeout, NetworkError, Retry).
2. **Couplage Fort et Évolution de Contrat (Breaking Changes)** :
   - Modification de la signature d'une fonction sur le serveur sans mettre à jour le client IDL Protobuf -> Observation du crash/rejet.

### Phase 4 : Interface CLI / Dashboard d'Expérimentation
- `cli_runner.py` / `main.py` : Menu interactif en console (Rich/Textual ou script simple) pour exécuter les tests, afficher les métriques et voir les messages réseau bruts en temps réel.

---

## 4. Plan de Vérification & Démonstration

### 1. Vérification des Fonctions
- Lancement du serveur custom RPC et exécution des appels distants via le Stub.
- Lancement du serveur gRPC et test des appels unaires et streaming.

### 2. Tests Comparatifs & Avantages/Inconvénients (Automatisés & Manuel)
- Exécuter `python main.py --benchmark` pour générer un tableau comparatif :
  - Taille du paquet (Octets) : JSON vs Protobuf
  - Temps moyen par appel (ms) : Local vs Custom RPC vs gRPC
- Exécuter la démo de simulation de panne : `python main.py --simulate-failures` pour observer la différence entre un appel local et un appel RPC soumis aux règles du réseau.
