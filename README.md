# SIMS 4 Mods Manager 💎

Gestionnaire de mods moderne, performant et automatisé pour **Les Sims 4**, conçu avec une **architecture 100% API REST (FastAPI)** et une **interface de bureau réactive (PySide6)**.

L'application centralise la recherche, le contournement des protections anti-bot (Cloudflare Turnstile), la résolution automatique des dépendances en cascade, le téléchargement, l'organisation intelligente des fichiers (`.package` et `.ts4script`), l'activation/désactivation en un clic et le suivi des mises à jour.

---

## ✨ Fonctionnalités Clés

- **🌐 100% Découplé via API REST** : L'interface graphique communique exclusivement avec une API REST interne documentée (`/docs`).
- **🛡️ Contournement Anti-Bot & Sessions** : Navigateur Playwright intégré pour la validation Cloudflare et la synchronisation des sessions LoversLab / Patreon.
- **📦 Installation Intelligente** : Extraction d'archives (`.zip`, `.rar`, `.7z`), validation DBPF et **respect strict de la règle de profondeur du moteur Sims 4** (les `.ts4script` sont automatiquement remontés au niveau 1).
- **🧩 Résolution de Dépendances** : Détection des prérequis (WickedWhims, Nisa's Wicked Perversions, etc.) catégorisés selon 4 statuts avec installation en cascade.
- **⚡ Mises à Jour en 1 Clic** : Détection différentielle de version et de date avec archivage de sauvegarde (rollback automatique en cas d'erreur).
- **🎛️ Activation / Désactivation Propre** : Désactivation non-destructive via renommage `.disabled` sans altérer vos fichiers d'origine.

---

## 🚀 Démarrage Rapide

### 1. Prérequis
- **Python** 3.11 à 3.13
- **uv** (Gestionnaire de paquets ultra-rapide) :
  ```powershell
  scoop install uv
  ```

### 2. Installation
```powershell
# Installation des dépendances du projet
uv sync

# Installation du navigateur Chromium pour l'anti-bot
uv run playwright install chromium
```

### 3. Lancement
```powershell
# Mode Interface Graphique (GUI par défaut)
uv run python run.py

# Ou Mode Serveur API Autonome (sans GUI)
uv run python run.py --server --port 8000
```
- **Interface Swagger** : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Interface ReDoc** : [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4. Tests & Vérification
```powershell
# Exécution de la suite de tests par module (115 tests - 100% vert, 0 warning)
uv run pytest tests/utils -v
uv run pytest tests/database -v
uv run pytest tests/api -v
uv run pytest tests/providers -v
uv run pytest tests/ui -v
uv run pytest tests/services -v

# Vérification du code avec le linter
uv run ruff check src/ tests/
```

---

## 📚 Documentation Complète

Pour explorer l'architecture détaillée, les spécifications techniques et les diagrammes du projet, consultez le dossier [`documentation/`](./documentation/) :

- **[Architecture & Organisation des Fichiers](./documentation/architecture.md)** : Principes Clean Architecture, découpage en couches et arborescence.
- **[Spécification de l'API REST](./documentation/api_reference.md)** : Endpoints, paramètres, DTOs Pydantic et protocole de streaming NDJSON.
- **[Schémas de Liaisons & Classes](./documentation/modules_and_classes.md)** : Diagrammes Mermaid du modèle de données, des services, des providers et de la séquence d'installation.
- **[Services Métier & Fournisseurs](./documentation/services_and_providers.md)** : Détails du scraping multithreadé, de la règle de profondeur `.ts4script`, et des connecteurs LoversLab / Patreon.
- **[Instructions Techniques & Retours d'Expérience](./INSTRUCTIONS.md)** : Règles métier avancées et bonnes pratiques.

---

## 📄 Licence
Ce projet est distribué sous licence GNU GPL v3. Voir le fichier [LICENSE](./LICENSE) pour plus d'informations.
