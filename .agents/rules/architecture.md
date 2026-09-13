# Architecture & Organisation du Code

## 1. Clean Architecture en 5 Couches
Le code source de `src/` est strictement structuré selon le principe de responsabilité unique et d'inversion de dépendance :

1. **Présentation** :
   - `src/api/routes/*_router.py` : Handlers FastAPI légers (validation HTTP, conversion de schémas, délégation).
   - `src/api/schemas/*.py` : Contrats de données Pydantic v2 découplés de la base de données.
   - `src/ui/` : Interface graphique PySide6 (vues, composants modulaires, cartes de mods, workers `QThread`).
2. **Services Métier (`src/services/*_service.py`)** :
   - Toute la logique applicative réside dans cette couche (`catalog_sync`, `mod_installer`, `mod_update`, `mod_toggle`, `dependency_resolver`, `game`).
   - Les services n'ont **aucune dépendance** vers l'UI ni vers FastAPI.
3. **Persistance (`src/database/`)** :
   - `models.py` (déclarations SQLAlchemy), `connection.py` (engine SQLite & session factory), `manager.py` (`DatabaseManager` avec repository pattern).
4. **Fournisseurs de Mods (`src/providers/<provider_name>/`)** :
   - Chaque provider (`loverslab`, `patreon`, etc.) est encapsulé dans son propre sous-dossier avec ses sous-modules dédiés (`scraper.py`, `downloader.py`, `parsers.py`, `matchers.py`, etc.) et hérite de `BaseSourceProvider`.
5. **Utilitaires Partagés (`src/utils/`)** :
   - Helpers transverses sans état (`logger.py`, `version_extractor.py`, `slug_utils.py`, `archive_extractor.py`, `game_dlc_matcher.py`, `mod_matcher.py`).

---

## 2. Règle du "Zéro Shim" (No Legacy Compatibility Stubs)
- Lors de toute refonte ou renommage de fichier, **supprimer immédiatement** les anciens fichiers au lieu de conserver des shims de redirection temporaires.
- Mettre à jour l'ensemble des imports du projet et de la suite de tests vers les modules canoniques finaux.
- Vérifier systématiquement avec `git status` et `uv run ruff check src/ tests/` qu'aucun import orphelin ou résiduel ne subsiste.

---

## 3. Prévention des Collisions d'Imports
- Dans `src/api/routes/__init__.py`, importer les modules de routeurs explicitement :
  ```python
  from src.api.routes import catalog_router, installed_mods_router, ...
  ```
- Ne **jamais** importer `from .catalog_router import router` avec un alias répété sous le même nom local, afin d'éviter les collisions silencieuses de namespace.

---

## 4. Injection de Dépendances FastAPI (`get_db`)
- Les routes FastAPI (`src/api/routes/*_router.py`) n'accèdent jamais directement à l'instance globale de `DatabaseManager`.
- Elles utilisent le pattern d'injection standard via `Depends(get_db)` défini dans `src/api/deps.py`.
- Cela garantit le découplage du cycle de vie des sessions SQLite et facilite le mocking unitaire.
