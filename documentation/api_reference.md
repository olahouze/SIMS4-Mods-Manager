# Spécification de l'API REST : SIMS 4 Mods Manager

Cette documentation présente l'ensemble des endpoints disponibles sur le serveur FastAPI du projet, leurs payloads de requête et leurs schémas de réponse.

---

## 🌐 Informations Générales

- **URL de base par défaut** : `http://127.0.0.1:8000/api`
- **Documentation interactive Swagger** : `http://127.0.0.1:8000/docs`
- **Documentation ReDoc** : `http://127.0.0.1:8000/redoc`
- **Format d'échange** : `application/json` (ou `application/x-ndjson` pour le streaming)

---

## 1. Comptes & Anti-Bot (`/api/accounts`)

Gère l'état des sessions utilisateurs pour les plateformes externes (LoversLab, Patreon), l'authentification assistée par Playwright et le contournement des protections anti-bot (Cloudflare Turnstile).

| Méthode | Route | Description | Code Succès |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/accounts` | Liste l'état des sessions pour LoversLab et Patreon | `200 OK` |
| `POST` | `/api/accounts/{provider}/test` | Vérifie la validité en direct de la session HTTP | `200 OK` |
| `POST` | `/api/accounts/{provider}/login` | Ouvre le navigateur Playwright pour connexion interactive | `200 OK` |
| `DELETE` | `/api/accounts/{provider}` | Supprime la session enregistrée et efface les cookies | `200 OK` |

### Modèle de Réponse : `AccountSessionItem`
```json
{
  "provider": "loverslab",
  "is_authenticated": true,
  "last_checked": "2026-09-05T14:30:00Z",
  "user_identifier": "Simmer123",
  "status_message": "Session valide"
}
```

---

## 2. Catalogue de Mods (`/api/catalog`)

Permet la recherche, le filtrage avancé, la synchronisation multithreadée et l'installation de mods.

| Méthode | Route | Description | Code Succès |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/catalog` | Recherche paginée avec filtres multicritères | `200 OK` |
| `POST` | `/api/catalog/sync` | Déclenche le scraping multi-sources en tâche de fond | `200 OK` |
| `GET` | `/api/catalog/sync/status` | Retourne la progression du scraping en temps réel | `200 OK` |
| `GET` | `/api/catalog/{id}/details` | Récupère la description complète, galeries et prérequis | `200 OK` |
| `POST` | `/api/catalog/check-dependencies` | Analyse la matrice des dépendances requises | `200 OK` |
| `POST` | `/api/catalog/install` | Installe un mod de manière synchrone | `200 OK` |
| `POST` | `/api/catalog/install-stream` | Installe un mod avec flux d'événements temps réel | `200 OK` |
| `GET` | `/api/catalog/thumbnail` | Sert l'image de miniature mise en cache localement | `200 OK` |

### Paramètres de Recherche (`GET /api/catalog`) :
- `search` (string, optionnel) : Titre, auteur ou tag recherché.
- `source` (string) : `loverslab`, `patreon`, ou `all`.
- `access` (string) : `public`, `unlocked`, `locked`, ou `all`.
- `status` (string) : `all`, `installed`, `not_installed`, `updates_available`.
- `sort` (string) : `recent` (date màj décroissante) ou `az` (titre alphabétique).
- `page` (int, défaut: 1) : Numéro de page.
- `limit` (int, défaut: 50, max: 200) : Nombre d'éléments par page.

### Protocole de Streaming d'Installation (`/api/catalog/install-stream`)
L'endpoint émet un flux `application/x-ndjson` d'objets JSON successifs :
```json
{"type": "progress", "percent": 15, "status": "Téléchargement en cours...", "details": "4.2 Mo • 1.8 Mo/s"}
{"type": "progress", "percent": 85, "status": "Extraction et validation DBPF...", "details": "Vérification ts4script"}
{"type": "finished", "success": true, "message": "Mod 'WickedWhims' installé avec succès."}
```

---

## 3. Mods Installés (`/api/installed`)

Gère les mods actuellement présents dans le dossier `Mods` des Sims 4.

| Méthode | Route | Description | Code Succès |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/installed` | Liste tous les mods installés avec statut et chemins | `200 OK` |
| `GET` | `/api/installed/{id}/dependents` | Liste les autres mods installés qui dépendent de ce mod | `200 OK` |
| `POST` | `/api/installed/scan` | Scanne et indexe automatiquement le dossier Mods | `200 OK` |
| `POST` | `/api/installed/{id}/toggle` | Active ou désactive un mod (`.disabled`) | `200 OK` |
| `DELETE` | `/api/installed/{id}` | Supprime physiquement un mod du disque et de la BDD | `200 OK` |
| `POST` | `/api/installed/open-folder` | Ouvre le dossier Mods ou d'un mod dans l'Explorateur Windows | `200 OK` |

### Schéma `InstalledModItem`
```json
{
  "id": 1,
  "catalog_mod_id": 42,
  "source": "loverslab",
  "remote_id": "3169",
  "title": "WickedWhims",
  "folder_name": "loverslab_WickedWhims_3169",
  "installed_files": ["loverslab_WickedWhims_3169/TurboDriver_WickedWhims_Scripts.ts4script"],
  "installed_date": "2026-09-01T10:00:00Z",
  "version_date": "2026-08-30T12:00:00Z",
  "version_str": "v175",
  "is_enabled": true,
  "author": "TURBODRIVER",
  "thumbnail_url": "https://...",
  "page_url": "https://www.loverslab.com/files/file/3169-wickedwhims/"
}
```

---

## 4. Mises à Jour (`/api/updates`)

Analyse comparative entre les versions installées et les dernières versions publiées sur les catalogues.

| Méthode | Route | Description | Code Succès |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/updates` | Détecte tous les mods installés obsolètes | `200 OK` |
| `POST` | `/api/updates/{id}` | Met à jour un mod unitaire (avec backup zip auto) | `200 OK` |
| `POST` | `/api/updates/all` | Met à jour l'ensemble des mods obsolètes | `200 OK` |
| `POST` | `/api/updates/batch` | Met à jour une liste d'IDs de mods sélectionnés | `200 OK` |

---

## 5. Paramètres & Système (`/api/settings`, `/api/system`, `/api/logs`)

| Méthode | Route | Description | Code Succès |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/settings` | Récupère la configuration courante et dossiers détectés | `200 OK` |
| `PATCH` | `/api/settings` | Met à jour les chemins personnalisés ou préférences | `200 OK` |
| `GET` | `/api/settings/database/stats` | Retourne la taille et les métriques de la base SQLite | `200 OK` |
| `POST` | `/api/settings/database/purge-catalog` | Vide le catalogue local pour réinitialiser le scraping | `200 OK` |
| `POST` | `/api/settings/cache/clear` | Purge le cache disque des miniatures d'images | `200 OK` |
| `POST` | `/api/game/launch` | Lance l'exécutable `TS4_x64.exe` si présent | `200 OK` |
| `GET` | `/api/logs` | Récupère le flux de logs applicatif avec filtres de niveau | `200 OK` |
| `DELETE` | `/api/logs` | Efface le tampon de logs en mémoire | `200 OK` |
| `POST` | `/api/logs/open-folder` | Ouvre le dossier local des fichiers logs | `200 OK` |
| `GET` | `/api/system/health` | Bilan de santé : Jeu, Mods, Base de données, Playwright | `200 OK` |
| `GET` | `/api/system/ping` | Endpoint de vérification de vivacité (liveness probe) | `200 OK` |
