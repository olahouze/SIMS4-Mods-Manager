# Instructions du Projet : Sims 4 Mods Manager

Ce document consigne les règles d'architecture, les contraintes techniques, les standards de code et les apprentissages clés acquis sur le projet pour guider les développements futurs.

---

## 1. Principes Directeurs & Architecture

### 1.1 Clean Architecture en 5 Couches
Le code source est strictement structuré selon le principe de responsabilité unique et d'inversion de dépendance :
1. **Présentation** :
   - `src/api/routes/*_router.py` : Handlers FastAPI minces (validation HTTP, conversion de schémas, délégation).
   - `src/api/schemas/*.py` : Contrats de données Pydantic v2 découplés de la BDD.
   - `src/ui/` : Interface graphique PySide6 (vues, composants, cartes, workers QThread).
2. **Services Métier (`src/services/*_service.py`)** :
   - Toute la logique applicative réside ici (`catalog_sync`, `mod_installer`, `mod_update`, `mod_toggle`, `dependency_resolver`, `game`).
   - Les services n'ont aucune dépendance vers l'UI ni vers FastAPI.
3. **Persistance (`src/database/`)** :
   - `models.py` (déclarations SQLAlchemy), `connection.py` (engine & session factory), `manager.py` (`DatabaseManager` avec repository pattern).
4. **Fournisseurs de Mods (`src/providers/<provider_name>/`)** :
   - Chaque provider (`loverslab`, `patreon`) est encapsulé dans son propre sous-dossier avec ses sous-modules dédiés (`provider.py`, `client.py`, `parser.py`, `models.py`, `matchers.py`).
5. **Utilitaires Partagés (`src/utils/`)** :
   - Helpers transverses sans état (`logger.py`, `version_extractor.py`, `slug_utils.py`, `archive_extractor.py`).

### 1.2 Règle du "Zéro Shim" (No Legacy Compatibility Stubs)
- Lors de toute refonte ou renommage de fichier, supprimer immédiatement les anciens fichiers au lieu de conserver des shims de redirection temporaires.
- Mettre à jour l'ensemble des imports du projet et de la suite de tests vers les modules canoniques finaux.
- Vérifier systématiquement avec `git status` et `ruff check` qu'aucun import orphelin ne subsiste.

### 1.3 Prévention des Collisions d'Imports
- Dans `src/api/routes/__init__.py`, importer les modules de routeurs explicitement :
  ```python
  from src.api.routes import catalog_router, installed_mods_router, ...
  ```
  Ne jamais importer `from .catalog_router import router` avec un alias répété sous le même nom local, sous peine de collisions silencieuses.

---

## 2. Scraping & Intégrations Providers

### 2.1 LoversLab : Authentification & Session Cloudflare
- L'authentification passe par un navigateur Playwright afin de résoudre les défis Cloudflare et d'extraire les cookies de session (`cf_clearance`, `ips4_IPSSessionFront`).
- Toutes les requêtes HTTP suivantes doivent impérativement réutiliser ces cookies ainsi que le `User-Agent` du navigateur sous peine de blocage 403.

### 2.2 Scraping Incrémental du Catalogue
- Le scraping s'exécute en tâche de fond.
- La première page doit être analysée, persistée en BDD et émise immédiatement pour un affichage instantané sans latence.
- En cas d'erreur de requête sur les pages suivantes, appliquer un délai d'attente exponentiel (backoff) avant nouvel essai pour éviter le bannissement d'IP.
- **Nettoyage des titres** : Nettoyer systématiquement les caractères invisibles (`\u200b`, `\ufeff`). Si le titre extrait est vide (`""`), extraire et reformater le titre à partir du slug de l'URL (`urllib.parse.unquote`).
- **Purge des mods fantômes** : Purger automatiquement de la base les références supprimées de la plateforme (ex. *"We could not locate the item you are trying to view"*).

### 2.3 Parallélisation par sous-catégorie
- Le scraping LoversLab est organisé par sous-catégories (174: WickedWhims, 201: Animations, 203: Clothing, etc.).
- **Un worker ThreadPoolExecutor indépendant par sous-catégorie** permet de paralléliser le scraping tout en maintenant le backoff exponentiel par catégorie.
- Lors de la fermeture de l'application (`ShutdownManager.trigger_shutdown()`), les workers d'arrière-plan doivent vérifier `ShutdownManager.is_shutting_down()` et quitter proprement pour éviter l'erreur *"cannot schedule new futures after interpreter shutdown"*.

### 2.4 Téléchargement & Résolution des Fichiers
- LoversLab propose soit des fichiers directs, soit des liens externes (Gofile, Mega, etc.). Le résolveur inspecte les en-têtes et le corps de la réponse.
- **Validation de l'archive avant extraction** : Toujours tester l'intégrité du fichier (`zipfile.is_zipfile(path)`) avant tentative d'extraction. Si le fichier téléchargé est une page web d'erreur ou de login (HTML), lever une exception claire et explicite.

### 2.5 Provider Patreon
- Architecture modulaire calquée sur LoversLab : `client.py` (appels HTTP / API Patreon), `parser.py` (posts et pièces jointes), `provider.py` (façade métier implémentant le contrat de synchronisation et téléchargement).

---

## 3. Détection & Résolution des Dépendances

### 3.1 Table de Correspondance & Détection Découplée
- **Table `SPECIAL_DEPENDENCY_CASES`** : Dans `src/services/dependency_resolver.py`, aucune valeur n'est codée en dur dans les branches du code. Une table de correspondance regroupe les cas spécifiques.
- **WickedWhims (ID `3169`)** : Actuellement le seul cas spécifique de la table, défini avec son URL canonique (`https://www.loverslab.com/files/file/3169-wickedwhims/`) et sa liste d'alias exhaustifs (`WW`, `ww`, avec/sans `-` ou `_` : `Wicked-Whims`, `wicked_whims`, `Wicked Whims`...).
- **Traitement standardisé** : Nisa's Wicked Perversions et tous les autres mods sont traités de la même manière que les autres dépendances (recherche automatique dans le catalogue BDD ou via `ModMatcher`).

### 3.2 Extraction HTML & Filtrage DLC EA
- Avant extraction de texte, remplacer les balises de bloc (`<br>`, `<p>`, `<div>`, `<li>`) par `\n` pour préserver les listes distinctes.
- **Filtrage des packs officiels EA** : Ignorer automatiquement les mentions de `DLC`, `Expansion Pack`, `Game Pack`, `Stuff Pack`, `Kit d'objets` qui ne sont pas des mods tiers.

### 3.3 Statuts de Dépendances dans l'UI
- Chaque dépendance affiche un statut explicite :
  - `INSTALLED` (✅ Installé)
  - `AVAILABLE` (⚠️ Trouvé dans le catalogue, non installé)
  - `SCANNING` (⏳ Vérification en cours)
  - `MISSING` (❌ Absent du catalogue)
- Si des dépendances sont manquantes, l'utilisateur a accès au bouton `⚠️ Installation Partielle` : l'installation n'est jamais bloquée arbitrairement, mais l'utilisateur est averti.

---

## 4. Contraintes Système de Fichiers (Les Sims 4)

### 4.1 Règle Cruciale : Profondeur des Fichiers `.ts4script`
- Les fichiers Python compilés du jeu (`.ts4script`) **ne doivent jamais dépasser 1 seul niveau de sous-dossier** dans `Documents/Electronic Arts/Les Sims 4/Mods`.
- Au-delà d'un niveau (`Mods/SousDossier/mon_script.ts4script`), le moteur C++ des Sims 4 ne les charge pas.
- Les fichiers `.package` supportent jusqu'à 5 niveaux, mais pour garantir la cohérence, chaque mod est installé dans son dossier racine dédié.

### 4.2 Nommage et Assainissement des Dossiers
- Format obligatoire : `{source}_{NomAssaini}_{xxx}` (ex: `loverslab_WickedWhims_1042`).
- Règle stricte : caractères alphanumériques et underscores uniquement (`[a-zA-Z0-9_]`).
- Supprimer systématiquement espaces, apostrophes, accents, diacritiques, emojis et signes de ponctuation.
- Le suffixe numérique aléatoire `_xxx` élimine les collisions lors de réinstallations.

---

## 5. Démarrage Rapide, Threads & Background Tasks

### 5.1 Démarrage Réactif (< 0.5s)
- Ne jamais lancer de recherche disque exhaustive synchrone lors de l'initialisation de l'application ou du serveur API.
- Les chemins du jeu (`TS4_x64.exe`) et du dossier `Mods` sont persistés dans `AppConfig` et vérifiés de façon asynchrone.

### 5.2 Synchronisation de l'État Réel (Daemon Worker)
- Un thread démon d'arrière-plan (`ModInstallerService.start_background_installed_mods_verifier()`) surveille les modifications manuelles de l'Explorateur Windows et purge les entrées orphelines.
- **Règle absolue** : Ne **jamais** appeler `verify_and_cleanup_installed_mods()` de manière synchrone dans un handler de route API (comme `GET /api/installed` ou `GET /api/updates`). Ce cleanup synchrone détruit les entrées de test et pénalise la latence HTTP.

### 5.3 Fermeture Propre (`ShutdownManager`)
- Déclenché via `ShutdownManager.trigger_shutdown()` lors du `closeEvent` de PySide6.
- Tous les workers et timers d'arrière-plan doivent interroger `ShutdownManager.is_shutting_down()` et s'interrompre proprement.

---

## 6. Base de Données & Optimisations de Requêtes

### 6.1 Prévention des Requêtes N+1
- Toujours précharger les collections de `CatalogMod` en une requête et construire des tables de hachage `by_id` et `by_key (source, remote_id)`.
- La résolution de mod installé privilégie la paire canonique `(source, remote_id)`, puis recourt à `catalog_mod_id` avec validation.

### 6.2 Modèles ORM
- `CatalogMod` : index distant (titre, version, URL, auteur, prérequis bruts et JSON).
- `InstalledMod` : instance locale sur disque (nom de dossier, version installée, source, lien optionnel vers `catalog_mod_id`).
- `Account` : identifiants et état de session (cookies Cloudflare, token) chiffrés.
- `AppSetting` : paires clé-valeur de configuration applicative.

---

## 7. Interface Utilisateur (PySide6)

### 7.1 Architecture Multi-Vues & Signaux Croisés
- Toute mutation d'état (installation, suppression, mise à jour) émet un signal connecté au coordinateur central `App._on_mods_state_changed()`.
- Ce gestionnaire met à jour de façon cohérente :
  - `InstalledView` (grille de tuiles `InstalledCard`)
  - `UpdatesView` (liste des versions supérieures détectées)
  - `CatalogView` (boutons d'installation basculés sur `✓ Déjà Installé`)
  - Le badge de notification de la barre de navigation
  - La vue détaillée ouverte le cas échéant

### 7.2 Ségrégation Threads UI / Tâches Asynchrones
- L'interface ne doit jamais exécuter d'I/O réseau, d'extraction zip ou de requêtes lourdes sur le thread principal PySide6.
- Utiliser systématiquement les workers `QThread` dédiés de `src/ui/workers/` (`CatalogFetchWorker`, `CatalogStatsWorker`, `ModDetailFetchWorker`).

---

## 8. Standards de Développement & Suite de Tests

### 8.1 Organisation des Tests
La suite de tests est organisée en miroirs stricts des packages de `src/` :
- `tests/api/` : Validation unitaire et intégration de chaque routeur FastAPI via `TestClient`.
- `tests/services/` : Tests unitaires de chaque service métier isolé avec mocks BDD/HTTP.
- `tests/database/` : Tests de connexion SQLite et opérations CRUD du `DatabaseManager`.
- `tests/providers/` : Tests des parseurs, extracteurs et clients LoversLab et Patreon.
- `tests/ui/` : Tests de robustesse des workers et signaux PySide6.
- `tests/utils/` : Tests des extracteurs de version, de slug et gestionnaires de logs.

### 8.2 Règle de Validation Obligatoire (Green State)
Avant chaque commit ou validation de tâche :
```bash
# 1. Analyse statique et linter (doit retourner 0 erreur)
uv run ruff check src/ tests/

# 2. Exécution des tests ÉLÉMENT PAR ÉLÉMENT en terminal visible (JAMAIS la suite globale d'un bloc ni en background)
uv run pytest tests/utils -v
uv run pytest tests/database -v
uv run pytest tests/api -v
uv run pytest tests/providers -v
uv run pytest tests/ui -v
uv run pytest tests/services -v
```

### 8.3 Isolation Stricte de la Base de Données de Test
- **Règle absolue** : Les tests automatisés ne doivent **jamais** polluer ni modifier la base de données réelle de l'utilisateur (`sims4_mods.db`).
- `src/core/config.py` lit la variable d'environnement `SIMS4_DB_PATH`.
- `tests/conftest.py` configure une fixture de session `isolate_test_database` créant une base temporaire dédiée pour toute la durée des tests, garantissant une étanchéité totale avec l'environnement utilisateur.

### 8.4 Exécution des Tests en Terminal Visible et par Module (Zéro Background Silencieux)
- **Interdiction Formelle du Bloc Global** : Ne JAMAIS lancer `pytest tests/` globalement en une seule commande, sous peine de gel/blocage des processus sur Windows.
- **Règle d'exécution par Élément** : Toujours exécuter les tests module par module (`tests/utils/`, `tests/database/`, `tests/api/`, `tests/providers/`, `tests/ui/`, `tests/services/`) ou fichier par fichier avec le mode verbeux explicite (`-v`, jamais `-q`).
- **Terminal Visible Synchrone (Zéro Background Tasks)** : Les commandes de test doivent impérativement s'exécuter de façon synchrone dans un terminal visible avec timeout (`WaitMsBeforeAsync: 10000`). Ne jamais déléguer l'exécution des tests à des background tasks silencieuses qui restent plantées.
- **Zéro Warning & Zero Live Network** : Aucun test ne doit interroger internet en direct sans mock. Tous les avertissements tiers doivent être filtrés ou corrigés pour garantir un statut 100% propre (0 warning).

---

## 9. Documentation Technique de Référence
Pour approfondir un sujet particulier, se référer aux documents détaillés dans le dossier [`documentation/`](file:///documentation/) :
- [Architecture & Guide des Dossiers](file:///documentation/architecture.md) : Principes d'organisation et découplage Clean Architecture.
- [Spécification Complète de l'API](file:///documentation/api_reference.md) : Endpoints REST, modèles Pydantic et streaming NDJSON.
- [Diagrammes de Classes & Relations](file:///documentation/modules_and_classes.md) : Modèles BDD, hiérarchie de services et diagrammes de séquence.
- [Services Métier & Fournisseurs](file:///documentation/services_and_providers.md) : Fonctionnement interne de chaque service et connecteur externe.
