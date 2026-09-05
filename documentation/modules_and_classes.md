# Schémas de Liaisons et Diagrammes de Classes

Ce document détaille les relations, contrats d'interface et flux d'interaction entre les différentes classes et modules de **SIMS 4 Mods Manager**.

---

## 📊 1. Modèle de Données (ORM SQLAlchemy)

```mermaid
classDiagram
    class CatalogMod {
        +int id
        +string source
        +string remote_id
        +string title
        +string author
        +string category
        +string page_url
        +string thumbnail_url
        +datetime published_date
        +datetime updated_date
        +string version_str
        +string patreon_status
        +string patreon_tier
        +string requirements_text
        +string requirements_status
        +string requirements_mods_json
        +get_tags_list() List~str~
        +get_download_urls_list() List~dict~
        +get_requirements_mods_list() List~dict~
    }

    class InstalledMod {
        +int id
        +int catalog_mod_id
        +string source
        +string remote_id
        +string title
        +string folder_name
        +string installed_files
        +datetime installed_date
        +datetime version_date
        +string version_str
        +bool is_enabled
        +get_installed_files_list() List~str~
        +set_installed_files_list(files)
    }

    class AccountSession {
        +string provider
        +string cookies_json
        +string user_agent
        +datetime last_authenticated
        +string user_identifier
        +bool is_valid
        +get_cookies_dict() dict
    }

    class AppSettings {
        +int id
        +string key
        +string value
        +datetime updated_at
    }

    CatalogMod "0..1" <-- "0..*" InstalledMod : catalog_mod_id
```

---

## ⚙️ 2. Couche Services & Orchestration

```mermaid
classDiagram
    class DatabaseManager {
        <<Singleton>>
        +get_instance() DatabaseManager
        +get_session() Session
        +get_catalog_mods_count() int
        +clean_and_repair_catalog() dict
        +purge_catalog() int
    }

    class CatalogSyncService {
        +run_catalog_sync(max_pages)
        +check_catalog_dependencies(mod_title, page_url, source)
    }

    class SyncTracker {
        <<ThreadSafe>>
        +bool is_running
        +int progress_percent
        +int total_scraped
        +dict categories
        +start(max_pages, categories_list)
        +record_page(new_count, is_first_page)
        +update_category(cat_id, pages, total, count, status)
        +finish(total_new)
        +set_error(msg)
        +to_response() CatalogSyncStatusResponse
    }

    class ModInstaller {
        +install_mod(payload, progress_cb) CatalogInstallResponse
        +perform_mod_install(payload, progress_cb) CatalogInstallResponse
        +sanitize_mod_folder_name(name) str
        +verify_installed_mods_on_disk()
    }

    class ModToggleManager {
        +toggle_mod(installed_mod_id, target_state) Tuple~bool, str~
    }

    class UpdateChecker {
        +check_has_update(installed_mod, catalog_mod) bool
        +update_mod(installed_id) Tuple~bool, str~
        +update_all_mods() Tuple~int, int~
    }

    class DependencyResolver {
        +resolve_mod_dependencies(reqs, session, remote_dict, title_dict) List~DependencyItem~
        +extract_requirements(html_text) Tuple~str, str, List~
    }

    class GameDetector {
        +detect_sims4_user_dir() Path
        +detect_mods_dir() Path
        +ensure_resource_cfg(mods_dir) Path
    }

    CatalogSyncService ..> SyncTracker : pilote
    CatalogSyncService ..> DatabaseManager : persiste
    ModInstaller ..> GameDetector : localise Mods/
    ModInstaller ..> DependencyResolver : cascade
    ModInstaller ..> DatabaseManager : enregistre
    ModToggleManager ..> GameDetector : renomme .disabled
    UpdateChecker ..> ModInstaller : délègue réinstallation
```

---

## 🔌 3. Couche Fournisseurs Externes (Providers)

```mermaid
classDiagram
    class BaseSourceProvider {
        <<Abstract>>
        +string provider_name
        +string display_name
        +string base_url
        +scrape_catalog(page, limit)* List~dict~
        +get_mod_details(mod_url)* dict
        +download_mod_file(download_url, dest, progress_cb)* Tuple~bool, str~
        +check_access(mod_data)* str
    }

    class LoversLabProvider {
        +CATEGORIES List~dict~
        +scrape_category_page(category, page) Tuple~List, int~
        +get_mod_details(mod_url) dict
        +download_mod_file(download_url, dest, progress_cb) Tuple~bool, str~
    }

    class LoversLabScraper {
        +scrape_category(category_id, page) List~dict~
        +parse_mod_page(html) dict
        +extract_requirements(html) Tuple
    }

    class LoversLabDownloader {
        +extract_download_candidates(soup, base_url) List~dict~
        +download_loverslab_file(url, dest, patreon_provider, progress_cb) Tuple
    }

    class PatreonProvider {
        +extract_post_id(url) str
        +check_post_access(post_url) dict
        +download_mod_file(url, dest, progress_cb) Tuple
    }

    class ProviderRegistry {
        <<Singleton>>
        +get_provider(name) BaseSourceProvider
        +list_providers() List~BaseSourceProvider~
    }

    BaseSourceProvider <|-- LoversLabProvider
    BaseSourceProvider <|-- PatreonProvider
    LoversLabProvider *-- LoversLabScraper : utilise
    LoversLabProvider *-- LoversLabDownloader : utilise
    ProviderRegistry o-- BaseSourceProvider : référence
```

---

## 🖥️ 4. Couche Interface Graphique & Workers Asynchrones

```mermaid
classDiagram
    class MainWindow {
        +ApiClient api_client
        +setup_navigation()
        +switch_view(view_index)
    }

    class CatalogView {
        +SyncTriggerWorker sync_worker
        +InstallWorker install_worker
        +on_search_changed()
        +on_install_clicked()
    }

    class ModDetailView {
        +FetchDetailsWorker details_worker
        +GalleryThumbWorker thumb_worker
        +DescriptionImageLoaderWorker img_worker
        +load_mod(mod_id, page_url)
    }

    class SyncTriggerWorker {
        <<QThread>>
        +Signal finished_signal(bool, str)
        +run()
    }

    class InstallWorker {
        <<QThread>>
        +Signal progress(int, str, str)
        +Signal finished(bool, str)
        +run()
    }

    class FetchDetailsWorker {
        <<QThread>>
        +Signal finished(dict)
        +Signal failed(str)
        +run()
    }

    class GalleryThumbWorker {
        <<QThread>>
        +Signal thumb_ready(int, QPixmap)
        +run()
    }

    class DescriptionImageLoaderWorker {
        <<QThread>>
        +Signal images_updated(str)
        +cancel()
        +run()
    }

    MainWindow *-- CatalogView
    MainWindow *-- ModDetailView
    CatalogView ..> SyncTriggerWorker : instancie
    CatalogView ..> InstallWorker : instancie
    ModDetailView ..> FetchDetailsWorker : instancie
    ModDetailView ..> GalleryBatchWorker : instancie
    ModDetailView ..> DescriptionImageLoaderWorker : instancie
    ModDetailView ..> ImageCache : consulte
    ModCard ..> ImageCache : consulte/alimente
    InstalledCard ..> ImageCache : consulte/alimente
```

---

## 🔄 5. Séquence d'Installation d'un Mod avec Dépendances

```mermaid
sequenceDiagram
    autonumber
    actor User as Utilisateur (PySide6)
    participant DetailView as ModDetailView
    participant ApiClient as ApiClient
    participant Router as CatalogRouter (/install-stream)
    participant Installer as ModInstallerService
    participant Resolver as DependencyResolver
    participant LL as LoversLabDownloader
    participant DB as DatabaseManager

    User->>DetailView: Clic sur "Installer"
    DetailView->>ApiClient: install_mod_stream(payload)
    ApiClient->>Router: POST /api/catalog/install-stream
    Router->>Installer: perform_mod_install(payload, progress_cb)
    
    Installer->>Resolver: resolve_mod_dependencies(cat_mod)
    Resolver-->>Installer: Liste des dépendances manquantes
    
    loop Pour chaque dépendance manquante
        Installer->>LL: download_loverslab_file(dep_url)
        LL-->>Installer: archive_dep.zip
        Installer->>Installer: Extraction & validation DBPF
        Installer->>DB: create_installed_mod(dep)
        Installer-->>Router: Event progress: "Dépendance installée"
        Router-->>ApiClient: NDJSON chunk
        ApiClient-->>DetailView: Signal progress.emit()
    end

    Installer->>LL: download_loverslab_file(mod_url)
    LL-->>Installer: mod_main.zip
    Installer->>Installer: Règle ts4script (profondeur max 1)
    Installer->>DB: create_installed_mod(main_mod)
    
    Installer-->>Router: Result: success=true
    Router-->>ApiClient: Event finished: success=true
    ApiClient-->>DetailView: Signal finished.emit()
    DetailView->>User: Affichage du badge "INSTALLÉ"
```
