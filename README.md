# SIMS 4 Mods Manager 💎

Application moderne et complète conçue en Python avec une **architecture 100% API REST (FastAPI)** et une **interface de bureau (PySide6)** pour centraliser, télécharger, organiser, activer/désactiver et mettre à jour les mods pour **Les Sims 4**.

> **Architecture 100% API** : Absolument toutes les actions de l'interface graphique (recherche, téléchargement, installation, scan, activation/désactivation, mise à jour, connexion et paramètres) passent par des endpoints API REST typés et documentés. Le programme s'exécute de manière unifiée au sein d'un même environnement Python.

---

## 📋 Prérequis

1. **Python** (version 3.11 à 3.13 recommandée)
2. **uv** (Gestionnaire de paquets ultra-rapide) :
   ```powershell
   # Si uv n'est pas installé (via Scoop ou installateur officiel)
   scoop install uv
   ```
3. **Navigateur Playwright (Chromium)** :
   Nécessaire pour l'authentification automatique, le contournement des protections anti-bot (Cloudflare Turnstile) et la validation du consentement adulte (+18 ans) sur les sites de mods.
   ```powershell
   uv run playwright install chromium
   ```
   *(Note : Si vous disposez déjà de Microsoft Edge ou Google Chrome sur votre système Windows, l'application est également capable de s'appuyer dessus automatiquement).*

---

## 🚀 Installation & Lancement

### 1. Installation des dépendances du projet
```powershell
uv sync
```

### 2. Installation des composants de navigation (Anti-Bot)
```powershell
uv run playwright install chromium
```

### 3. Lancement de l'application (Mode GUI par défaut)
```powershell
uv run python run.py
```
*Le programme vérifie la disponibilité du port `8000` (ou alloue automatiquement le premier port libre s'il est occupé), démarre le serveur API en tâche de fond et lance l'interface graphique PySide6 connectée au serveur API.*

### 4. Lancement en Mode Serveur Autonome (API REST sans GUI)
Pour utiliser l'application comme un serveur API REST autonome (accessible depuis un navigateur, Swagger UI, ReDoc ou des scripts externes) :
```powershell
uv run python run.py --server
```
Options disponibles :
- `--server`, `--api`, `--headless` : Active le mode serveur autonome.
- `--port <PORT>` : Spécifie un port initial (défaut : `8000`). En cas d'indisponibilité, le programme bascule automatiquement sur un port libre.
- `--host <IP>` : Spécifie l'adresse d'écoute (défaut : `127.0.0.1`).

**Documentation Swagger interactive** : `http://127.0.0.1:8000/docs`  
**Documentation ReDoc** : `http://127.0.0.1:8000/redoc`

### 5. Exécution des tests automatisés
```powershell
uv run pytest
```

---

## 🌐 Cartographie des Endpoints API REST

Toutes les actions possibles dans l'interface graphique disposent de leur équivalent en API REST :

| Module | Méthode & Route | Description |
| :--- | :--- | :--- |
| **Comptes & Anti-Bot** | `GET /api/accounts` | Liste les états de session pour LoversLab et Patreon |
| | `POST /api/accounts/{provider}/test` | Teste la validité de la session en direct |
| | `POST /api/accounts/{provider}/login` | Lance le navigateur interactif pour Cloudflare / connexion |
| | `DELETE /api/accounts/{provider}` | Réinitialise la session et supprime les cookies |
| **Catalogue** | `GET /api/catalog` | Recherche, filtres (source, accès, statut, tri) et pagination |
| | `POST /api/catalog/sync` | Déclenche la synchronisation multi-sources (1 à 20 pages) |
| | `GET /api/catalog/sync/status` | Suivi de la progression du scraping en temps réel |
| | `POST /api/catalog/install` | Télécharge et installe un mod (respect règle profondeur `.ts4script`) |
| | `GET /api/catalog/thumbnail` | Sert et met en cache la miniature d'un mod |
| **Mes Mods** | `GET /api/installed` | Liste les mods installés, actifs/inactifs et détails |
| | `POST /api/installed/{id}/toggle` | Active ou désactive un mod (`.disabled`) |
| | `DELETE /api/installed/{id}` | Désinstalle un mod et supprime ses fichiers |
| | `POST /api/installed/scan` | Indexe automatiquement les mods ajoutés manuellement |
| | `POST /api/installed/open-folder` | Ouvre le dossier Mods ou d'un mod dans l'Explorateur Windows |
| **Mises à Jour** | `GET /api/updates` | Détecte les mods installés ayant une nouvelle version |
| | `POST /api/updates/{id}` | Met à jour un mod spécifique avec backup auto |
| | `POST /api/updates/all` | Met à jour tous les mods obsolètes en 1 clic |
| **Paramètres** | `GET /api/settings` | Récupère la configuration et chemins détectés |
| | `PATCH /api/settings` | Met à jour les paramètres de l'application |
| | `POST /api/settings/cache/clear` | Vide le cache des miniatures |
| | `POST /api/game/launch` | Lance l'exécutable Les Sims 4 |
| **Logs & Santé** | `GET /api/logs` | Récupère les logs avec filtres par niveau et recherche |
| | `DELETE /api/logs` | Efface l'historique des logs en mémoire |
| | `POST /api/logs/open-folder` | Ouvre le dossier local des logs |
| | `GET /api/system/health` | Diagnostic de santé (jeu, mods, base de données, Playwright) |

---

## 📂 Structure du Projet

```
SIMS4-Mods-Manager/
├── pyproject.toml              # Dépendances du projet (uv, FastAPI, PySide6, etc.)
├── run.py                      # Point d'entrée unique (Mode GUI ou Mode --server)
├── src/
│   ├── api/                    # Couche API REST 100% découplée
│   │   ├── app.py              # Instance FastAPI, middlewares CORS, routers
│   │   ├── client.py           # ApiClient HTTP utilisé par toutes les vues GUI
│   │   ├── models.py           # Schémas Pydantic typés pour requêtes et réponses
│   │   ├── server.py           # Gestionnaire Uvicorn (thread daemon ou standalone)
│   │   └── routes/             # Endpoints (accounts, catalog, installed, updates, settings, logs, system)
│   ├── core/                   # Logique métier
│   │   ├── config.py           # Configuration globale & chemins d'accès
│   │   ├── database.py         # Modèles SQLite (CatalogMod, InstalledMod, AccountSession)
│   │   ├── game_detector.py    # Détection du jeu multi-langues & registre
│   │   ├── mod_installer.py    # Extraction, profondeur ts4script & sauvegardes
│   │   ├── mod_toggle.py       # Activation / désactivation (.disabled)
│   │   └── session_manager.py  # Gestion Playwright & client HTTP rapide curl_cffi
│   ├── providers/              # Fournisseurs de contenu (LoversLab, Patreon)
│   ├── ui/                     # Interface graphique (consomme exclusivement l'API via ApiClient)
│   │   ├── app.py              # Fenêtre principale connectée à l'API
│   │   ├── components/         # ModCard, FilterBar, Badges, ProgressDialog
│   │   └── views/              # Comptes, Catalogue, Installés, MàJ, Paramètres, Logs
│   └── utils/
│       ├── archive.py          # Gestion des archives (.zip, .rar, .7z)
│       ├── logger.py           # Logger avec émetteur Qt en temps réel
│       ├── network.py          # Détection et allocation dynamique de port libre
│       └── resource_cfg.py     # Configuration Resource.cfg
└── tests/                      # Suite de tests (Core, API, ApiClient, Network)
```
