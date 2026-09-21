# Spécification des API Internes (Back-to-Back Architecture)

Ce document décrit les **API Internes** de l'application SIMS 4 Mods Manager. Contrairement aux API REST publiques accessibles par le Front-End, ces API représentent les contrats d'interfaces programmatiques stricts assurant la communication étanche entre les couches applicatives internes et les modules d'infrastructure.

---

## 1. Principe de l'API Interne

Dans une architecture Clean/Hexagonale, les services métier ne doivent jamais manipuler directement des sessions de base de données (ex: SQLAlchemy `Session`), ni exécuter des requêtes SQL ad-hoc.

Chaque ressource d'infrastructure expose une **API Interne** sous forme d'interface abstraite (`Protocol` ou `ABC`).

### Règles d'Échéance & Sécurité :
1. **Inaccessibilité depuis le Front-End** : Les interfaces et classes de repositories ne sont jamais importées dans `src/ui/`.
2. **Indépendance Vis-à-Vis des Frameworks** : Les entités renvoyées par les méthodes de ces API sont des entités de domaine pures (`InstalledModEntity`, `CatalogModEntity`, `AccountSessionEntity`), détachées de l'ORM SQLAlchemy.
3. **Mappage Automatisé** : La classe `ModelMapper` se charge de la sérialisation / désérialisation bidirectionnelle entre l'ORM et le Domaine.

---

## 2. Référentiel des Interfaces d'API Internes

### `IInstalledModRepository`
Emplacement : `src/domain/interfaces/repositories/mod_repository_interface.py`
Implémentation concrète : `SqlAlchemyInstalledModRepository`

| Méthode | Signature | Description |
| :--- | :--- | :--- |
| `get_by_id` | `(mod_id: int) -> Optional[InstalledModEntity]` | Recherche un mod installé par son ID unique. |
| `get_by_folder_name` | `(folder_name: str) -> Optional[InstalledModEntity]` | Recherche un mod par son nom de dossier local. |
| `get_by_source_and_remote_id` | `(source: str, remote_id: str) -> Optional[InstalledModEntity]` | Recherche par source (ex: LoversLab) et ID distant. |
| `get_all` | `(enabled_only: Optional[bool] = None) -> list[InstalledModEntity]` | Liste l'ensemble des mods avec filtrage optionnel d'activation. |
| `save` | `(entity: InstalledModEntity) -> InstalledModEntity` | Crée ou met à jour un enregistrement de mod installé. |
| `delete_by_id` | `(mod_id: int) -> bool` | Supprime un enregistrement en base de données. |
| `set_enabled` | `(mod_id: int, is_enabled: bool) -> bool` | Met à jour l'état actif/inactif d'un mod. |
| `count` | `() -> int` | Nombre total de mods installés. |

---

### `ICatalogRepository`
Emplacement : `src/domain/interfaces/repositories/catalog_repository_interface.py`
Implémentation concrète : `SqlAlchemyCatalogRepository`

| Méthode | Signature | Description |
| :--- | :--- | :--- |
| `get_by_id` | `(mod_id: int) -> Optional[CatalogModEntity]` | Récupère une fiche du catalogue par son ID. |
| `get_by_source_and_remote_id` | `(source: str, remote_id: str) -> Optional[CatalogModEntity]` | Récupère une fiche par sa source et son identifiant distant. |
| `search` | `(query, category, author, source, access, status, mod_type, sort, limit, offset) -> tuple[list[CatalogModEntity], int]` | Recherche multicritère paginée avec filtres et comptage. |
| `get_all` | `(limit: Optional[int], offset: int) -> list[CatalogModEntity]` | Retourne l'ensemble des fiches catalogue. |
| `save` | `(entity: CatalogModEntity) -> CatalogModEntity` | Sauvegarde une fiche catalogue unique. |
| `save_batch` | `(entities: list[CatalogModEntity]) -> int` | Sauvegarde en masse un lot de fiches dans une seule transaction. |
| `update_requirements_overrides`| `(mod_id: int, overrides: dict[str, str]) -> bool` | Met à jour les classifications manuelles de dépendances. |
| `get_categories` | `() -> list[str]` | Liste les catégories uniques du catalogue. |
| `count` | `() -> int` | Nombre total de mods répertoriés. |

---

### `IAccountRepository`
Emplacement : `src/domain/interfaces/repositories/account_repository_interface.py`
Implémentation concrète : `SqlAlchemyAccountRepository`

| Méthode | Signature | Description |
| :--- | :--- | :--- |
| `get_by_provider` | `(provider_name: str) -> Optional[AccountSessionEntity]` | Récupère la session et cookies d'un fournisseur. |
| `get_all` | `() -> list[AccountSessionEntity]` | Liste toutes les sessions enregistrées. |
| `save` | `(entity: AccountSessionEntity) -> AccountSessionEntity` | Enregistre ou met à jour une session. |
| `delete` | `(provider_name: str) -> bool` | Supprime une session existante. |

---

## 3. Façade d'Extraction d'Archives (`ArchiveExtractor`)
Emplacement : `src/infrastructure/filesystem/archive_extractor.py`

L'infrastructure de manipulation des fichiers d'archives est unifiée derrière le pattern Strategy :
- `ZipArchiveHandler`
- `SevenZipArchiveHandler`
- `RarArchiveHandler`

L'accès à l'extraction s'effectue via l'API orientée objet `ArchiveExtractor.extract(archive_path, dest_dir)`.
