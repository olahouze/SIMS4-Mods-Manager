# Services Métier & Fournisseurs Externes (Providers)

Ce document détaille le fonctionnement interne de la couche **Services (`src/services/`)** et de la couche **Providers (`src/providers/`)**.

---

## 🛠️ 1. Services Métier (`src/services/`)

La couche de services encapsule l'ensemble des règles métier applicatives. Elle est totalement indépendante du protocole HTTP (FastAPI) et de l'interface graphique (PySide6).

### 1.1 `catalog_sync_service.py` (Synchronisation du Catalogue)
- **Rôle** : Orchestre le scraping en tâche de fond des catégories LoversLab.
- **Multithreading par Sous-Catégorie** : Un pool `ThreadPoolExecutor` indépendant gère chaque catégorie (14 catégories actives, ex. WickedWhims, Animations, Clothing, Objects...).
- **Backoff Exponentiel** : En cas d'erreur réseau ou de ralentissement de la plateforme cible, le worker applique un délai croissant (`2s * 2^attempt`) pour éviter les bannissements d'adresse IP.
- **`SyncTracker` (Thread-Safe)** : Singleton avec verrou mutex (`threading.Lock()`) maintenant l'état en direct du scraping : pourcentage global, pages complétées, mods indexés par sous-catégorie, message d'état et erreurs.
- **Arrêt Gracieux** : Tous les workers vérifient `ShutdownManager.is_shutting_down()` et `SyncTracker.stop_requested` pour s'interrompre instantanément lors de la fermeture de l'application.

---

### 1.2 `mod_installer_service.py` (Installation & Règle Critique `.ts4script`)
- **Règle d'or du moteur des Sims 4** :
  - Les fichiers `.package` peuvent être imbriqués jusqu'à **5 sous-dossiers** de profondeur (grâce au fichier `Resource.cfg` configuré).
  - Les fichiers de script Python compilés **`.ts4script` NE DOIVENT PAS être situés à plus de 1 niveau de profondeur** (`Mods/<DossierDuMod>/script.ts4script`).
- **Correction Automatique de Profondeur** :
  Si une archive contient des fichiers `.ts4script` logés dans des arborescences profondes (ex. `Archive/Sub/Deep/script.ts4script`), l'installeur les remonte automatiquement à la racine du dossier du mod (`Mods/nom_du_mod/script.ts4script`).
- **Validation DBPF** : Vérifie l'en-tête binaire (`DBPF` magic header) des fichiers `.package` pour détecter les téléchargements corrompus ou les pages HTML déguisées.
- **Cascade de Dépendances** : Si l'option est cochée, le service résout et installe automatiquement les dépendances requises avant d'installer le mod principal.

---

### 1.3 `mod_update_service.py` (Mises à Jour & Sécurité Rollback)
- **Détection Différentielle de Versions** :
  Un mod installé est considéré comme obsolète si :
  1. La date de mise à jour sur le catalogue (`updated_date`) est postérieure à la date d'installation (`version_date`).
  2. Ou la chaîne de version (`version_str`) est différente entre la base locale et le catalogue distant.
- **Sauvegarde Automatique de Rollback** :
  Avant toute mise à jour ou écrasement de dossier, le service compresse le dossier existant dans un fichier ZIP d'archive (`.sims4_mod_manager/backups/`). En cas d'échec de téléchargement de la nouvelle version, l'ancienne version est restaurée automatiquement.

---

### 1.4 `mod_toggle_service.py` (Activation / Désactivation Propre)
- **Principe Non-Destructif** : L'utilisateur peut désactiver un mod sans le supprimer du disque, évitant ainsi de devoir le re-télécharger.
- **Mécanisme d'Extension `.disabled`** :
  - Désactivation : renomme tous les fichiers `.package` $\rightarrow$ `.package.disabled` et `.ts4script` $\rightarrow$ `.ts4script.disabled`. Le moteur du jeu ignore complètement ces fichiers.
  - Activation : retire l'extension `.disabled` pour rétablir les noms de fichiers initiaux.
- **Synchronisation BDD** : Met à jour le booléen `is_enabled` dans la table `installed_mods`.

---

### 1.5 `dependency_resolver.py` (Résolution des Dépendances)
Catégorise chaque prérequis d'un mod dans l'un des **4 statuts stricts** :

| Statut | Signification | Comportement UI |
| :--- | :--- | :--- |
| `INSTALLED` | Présent dans le dossier `Mods/` | Badge vert, prêt |
| `DETECTED_NOT_INSTALLED` | Présent dans le catalogue mais pas encore installé | Badge bleu, téléchargeable en 1 clic |
| `NOT_DETECTED_SCANNING` | Non trouvé, mais le scraping catalogue est toujours en cours | Badge orange animé "Scan en cours..." |
| `NOT_DETECTED_FINISHED` | Non trouvé et le catalogue a fini d'être parcouru | Badge rouge "Non trouvé" (lien externe ou mod tiers) |

- **Détection des Dépendances Inverses (`find_dependent_installed_mods`)** :
  Permet d'identifier tous les mods installés qui dépendent d'un mod donné avant sa suppression, afin d'afficher une boîte de dialogue d'avertissement explicite listant les mods qui cesseront de fonctionner.
- **Table de Correspondance pour Cas Spécifiques (`SPECIAL_DEPENDENCY_CASES`)** :
  Aucune valeur n'est codée en dur dans les branches conditionnelles du code. Actuellement, seul **WickedWhims** fait l'objet d'un cas spécifique répertorié dans la table de correspondance avec son URL fixe (`https://www.loverslab.com/files/file/3169-wickedwhims/`), son ID `3169` et sa liste d'alias exhaustifs (`WW`, `ww`, avec/sans `-` ou `_` : `Wicked-Whims`, `wicked_whims`, etc.).
  Tous les autres mods (y compris Nisa's Wicked Perversions) sont traités de manière homogène via le catalogue BDD ou l'algorithme de distance textuelle (`ModMatcher`).

---

### 1.6 `game_service.py` (Détection Sims 4 & `Resource.cfg`)
- **Détection Multi-Langues du Dossier Utilisateur** :
  Sur Windows, le dossier Documents des Sims 4 varie selon la langue d'installation du système :
  - Français : `Documents/Electronic Arts/Les Sims 4/Mods`
  - Anglais : `Documents/Electronic Arts/The Sims 4/Mods`
  - Allemand : `Documents/Electronic Arts/Die Sims 4/Mods`
  - Espagnol : `Documents/Electronic Arts/Los Sims 4/Mods`
  - Espaces insécables (`\u00a0`) fréquemment générés par Origin/EA App.
- **Gestion du `Resource.cfg`** :
  Vérifie et crée si nécessaire le fichier `Resource.cfg` standard permettant au jeu de charger les mods jusqu'à 5 sous-dossiers :
  ```ini
  Priority 500
  PackedFile *.package
  PackedFile */*.package
  PackedFile */*/*.package
  PackedFile */*/*/*.package
  PackedFile */*/*/*/*.package
  ```

---

## 🌐 2. Fournisseurs de Contenu (`src/providers/`)

### 2.1 LoversLab (`src/providers/loverslab/`)
- **[parsers.py](file:///d:/Workspace/Github/OLAHOUZE/SIMS4-Mods-Manager/src/providers/loverslab/parsers.py)** :
  - Fonctions pures de parsing HTML BeautifulSoup complètement découplées des couches réseau.
  - `extract_gallery_screenshots(soup, base_url)` : extrait les URLs d'images haute résolution des carrousels, lightboxes et miniatures.
  - `sanitize_description_html(content_elem, base_url)` : nettoie les scripts, changelogs, styles d'auteurs et résout les URLs absolues.
- **[scraper.py](file:///d:/Workspace/Github/OLAHOUZE/SIMS4-Mods-Manager/src/providers/loverslab/scraper.py)** :
  - Orchestre les requêtes HTTP avec le pool de sessions `SessionManager`.
  - Parcourt les 14 sous-catégories LoversLab avec pagination intelligente.
- **[downloader.py](file:///d:/Workspace/Github/OLAHOUZE/SIMS4-Mods-Manager/src/providers/loverslab/downloader.py)** :
  - Évalue les candidats de téléchargement : priorise les archives directes (`.zip`, `.package`) avec taille en Mo/Go sur les liens externes.
  - Résout les pages de confirmation multi-étapes d'Invision Power Board (`?do=download&confirm=1`).
  - Détecte les hébergeurs tiers (Mega, MediaFire, Google Drive, SimFileShare) et informe l'utilisateur si un téléchargement automatisé direct est impossible.

### 2.2 Patreon (`src/providers/patreon/`)
- **[provider.py](file:///d:/Workspace/Github/OLAHOUZE/SIMS4-Mods-Manager/src/providers/patreon/provider.py)** :
  - Interroge l'API interne Patreon (`/api/posts/{post_id}`) à l'aide de la session authentifiée `curl_cffi`.
  - Analyse l'accessibilité : `PUBLIC`, `UNLOCKED` (débloqué par l'abonnement en cours) ou `LOCKED` (nécessite un tier payant, affichage du montant mensuel).
  - **Rejet des Faux Liens de Téléchargement** : Filtre les pièces jointes pour rejeter les simples images de couverture (`.png`, `.jpg`) et sélectionner exclusivement les archives Sims 4.
