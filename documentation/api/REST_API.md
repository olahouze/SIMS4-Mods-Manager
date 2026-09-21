# Spécification de l'API REST Externe (Front -> Back Gateway)

Ce document fournit la documentation complète de l'API REST de **SIMS 4 Mods Manager**, propulsée par **FastAPI** et **Uvicorn**.

---

## 1. Vue d'Ensemble & Documentation Interactive

- **Serveur local par défaut** : `http://127.0.0.1:8000`
- **Préfixe des routes** : `/api`
- **Swagger UI (Interactive)** : `http://127.0.0.1:8000/docs`
- **ReDoc (Spécification OpenAPI)** : `http://127.0.0.1:8000/redoc`
- **Format d'échange** : JSON (UTF-8) pour les requêtes/réponses standard, NDJSON pour les flux de streaming (`/install-stream`).

---

## 2. Référentiel des Endpoints

### 2.1. Catalogue Distant (`/api/catalog`)

#### `GET /api/catalog`
Retourne la liste paginée des mods du catalogue avec filtres multicritères.
- **Paramètres Query** :
  - `search` *(str, optionnel)* : Recherche textuelle dans le titre, l'auteur ou les tags.
  - `source` *(str, optionnel)* : `loverslab`, `patreon`, ou `all`.
  - `access` *(str, optionnel)* : `public`, `unlocked`, `locked`, ou `all`.
  - `status` *(str, optionnel)* : `all`, `installed`, `not_installed`, ou `updates_available`.
  - `mod_type` *(str, optionnel)* : `animation`, `clothing`, `hair`, `body_skin`, etc.
  - `sort` *(str, défaut: "recent")* : `recent` ou `az`.
  - `page` *(int, défaut: 1)* : Numéro de page (>= 1).
  - `limit` *(int, défaut: 50)* : Éléments par page (1 à 200).
- **Réponse 200** : `CatalogListResponse` `{ total: int, page: int, limit: int, items: List[CatalogModItem] }`

#### `GET /api/catalog/{mod_id}` & `GET /api/catalog/{mod_id}/details`
Récupère les informations complètes d'un mod (description formatée, captures d'écran, liste résolue des dépendances).
- **Paramètres Path** : `mod_id` *(int)*
- **Paramètres Query** : `force_refresh` *(bool, optionnel)*
- **Réponse 200** : `ModDetailsResponse`

#### `POST /api/catalog/sync`
Déclenche la synchronisation multi-sources en arrière-plan via le `ThreadPoolManager`.
- **Corps JSON** : `CatalogSyncRequest` `{ max_pages: int }`
- **Réponse 200** : `CatalogSyncStatusResponse`

#### `GET /api/catalog/sync/status`
Consulte l'état de progression en temps réel du scraping.
- **Réponse 200** : `CatalogSyncStatusResponse` `{ is_running: bool, current_page: int, total_pages: int, ... }`

#### `POST /api/catalog/sync/pause` | `resume` | `stop`
Met en pause, reprend ou stoppe la synchronisation en cours.

#### `POST /api/catalog/check-dependencies`
Analyse le graphe de dépendances d'un mod avant téléchargement.
- **Corps JSON** : `CatalogInstallRequest` `{ catalog_mod_id?: int, source?: str, remote_id?: str, ... }`
- **Réponse 200** : `DependenciesCheckResponse` `{ can_install: bool, is_partial: bool, dependencies: List[...] }`

#### `POST /api/catalog/install`
Télécharge et installe un mod et optionnellement ses dépendances manquantes.
- **Corps JSON** : `CatalogInstallRequest`
- **Réponse 200** : `CatalogInstallResponse` `{ success: bool, message: str, installed_folder: str }`

#### `POST /api/catalog/install-stream`
Installe un mod en diffusant les événements de progression en flux continu (`application/x-ndjson`).

#### `GET /api/catalog/thumbnail`
Télécharge et met en cache l'image vignette d'un mod distant.

---

### 2.2. Mods Installés (`/api/installed`)

#### `GET /api/installed`
Liste l'ensemble des mods installés dans le dossier `Mods` des Sims 4, avec statistiques d'activation et statut de mise à jour.
- **Paramètres Query** : `search` *(str, optionnel)*
- **Réponse 200** : `InstalledListResponse` `{ total: int, enabled_count: int, disabled_count: int, items: List[InstalledModItem] }`

#### `POST /api/installed/{mod_id}/toggle`
Active ou désactive un mod sans le supprimer du disque (renommage en `.disabled`).
- **Paramètres Path** : `mod_id` *(int)*
- **Corps JSON** : `InstalledToggleRequest` `{ enabled?: bool }`
- **Réponse 200** : `InstalledToggleResponse` `{ success: bool, message: str, is_enabled: bool }`

#### `DELETE /api/installed/{mod_id}`
Supprime définitivement les fichiers du mod sur le disque et son entrée en BDD.
- **Paramètres Path** : `mod_id` *(int)*
- **Réponse 200** : `InstalledUninstallResponse` `{ success: bool, message: str }`

#### `GET /api/installed/{mod_id}/dependents`
Liste les autres mods installés qui dépendent de ce mod (pour alerte avant suppression).
- **Paramètres Path** : `mod_id` *(int)*
- **Réponse 200** : `ModDependentsResponse`

#### `POST /api/installed/scan`
Scanne le répertoire local `Mods` pour indexer les ajouts ou suppressions manuelles.
- **Réponse 200** : `InstalledScanResponse`

#### `POST /api/installed/open-folder`
Ouvre le dossier racine des mods ou le dossier spécifique d'un mod dans l'explorateur de fichiers.
- **Corps JSON** : `InstalledOpenFolderRequest` `{ folder_name?: str }`
- **Réponse 200** : `InstalledOpenFolderResponse`

---

### 2.3. Comptes & Anti-Bot (`/api/accounts`)

#### `GET /api/accounts`
Liste le statut des sessions de comptes pour LoversLab et Patreon.
- **Réponse 200** : `AccountListResponse`

#### `POST /api/accounts/{provider_name}/test`
Teste la validité des cookies de session d'un fournisseur en effectuant une requête en direct.

#### `POST /api/accounts/{provider_name}/login`
Lance une fenêtre de navigateur Playwright pour résolution Cloudflare ou saisie des identifiants.

#### `DELETE /api/accounts/{provider_name}`
Réinitialise et efface les cookies et le profil de navigateur associé.

---

### 2.4. Mises à Jour (`/api/updates`)

#### `GET /api/updates`
Liste tous les mods installés ayant une nouvelle version disponible dans le catalogue.
- **Réponse 200** : `UpdatesListResponse`

#### `POST /api/updates/{installed_id}`
Met à jour un mod unique en téléchargeant la dernière version.

#### `POST /api/updates/all` & `POST /api/updates/batch`
Met à jour l'ensemble des mods ou une sélection spécifique en tâche de fond.

---

### 2.5. Système & Paramètres (`/api/system` & `/api/settings`)

#### `GET /api/system/health`
Vérifie la santé de l'API, de la base de données SQLite et de l'environnement Playwright.

#### `GET /api/settings` & `POST /api/settings`
Lecture et mise à jour de la configuration utilisateur (`AppConfig`).
