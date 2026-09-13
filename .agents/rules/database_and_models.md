# Base de Données & Modélisation SQLAlchemy

## 1. Prévention des Requêtes N+1
- Toujours précharger les collections d'entités (notamment `CatalogMod` et `InstalledMod`) en une seule requête groupée et construire des dictionnaires de recherche en mémoire (`by_id`, `(source, remote_id)`, `by_title`).
- La résolution de mod installé privilégie la paire canonique `(source, remote_id)`, puis recourt à `catalog_mod_id` avec validation.

---

## 2. Modèles ORM Canoniques
- `CatalogMod` : Mod distant référencé (titre, version, URL de page, auteur, liens de téléchargement, tags, prérequis textuels et liste JSON `requirements_mods_json`).
- `InstalledMod` : Mod local présent sur le disque (nom de dossier, liste des fichiers `.package` et `.ts4script`, état activé/désactivé, lien optionnel vers `catalog_mod_id`).
- `AccountSession` : Identifiants, cookies de session chiffrés / anti-bot et métadonnées d'authentification par fournisseur (`loverslab`, `patreon`).
- `AppSetting` : Table clé-valeur pour les préférences globales de l'utilisateur.

---

## 3. Pragmas SQLite & Concurrence
- L'accès à SQLite utilise le mode WAL (`PRAGMA journal_mode=WAL;`) et des verrous adaptés via `DatabaseManager` pour autoriser des lectures concurrentes rapides pendant les écritures d'arrière-plan.
