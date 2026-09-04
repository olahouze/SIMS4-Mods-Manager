# Instructions du Projet : Sims 4 Mods Manager

Ce document consigne les règles d'architecture, les contraintes techniques et les apprentissages clés acquis sur le projet pour guider les développements futurs.

---

## 1. Scraping & Intégration LoversLab

### 1.1 Authentification & Session Cloudflare
- L'authentification passe par un navigateur Playwright afin de résoudre les défis Cloudflare et d'extraire les cookies de session (`cf_clearance`, `ips4_IPSSessionFront`).
- Toutes les requêtes HTTP suivantes doivent impérativement réutiliser ces cookies ainsi que le `User-Agent` du navigateur sous peine de blocage 403.

### 1.2 Scraping Incrémental du Catalogue
- Le scraping des pages du catalogue s'exécute en tâche de fond.
- La première page doit être analysée, persistée en BDD et affichée immédiatement pour un rendu sans latence.
- En cas d'erreur de requête sur les pages suivantes, appliquer un délai d'attente exponentiel (backoff) avant nouvel essai pour éviter le bannissement d'IP.
- **Nettoyage des titres** : Nettoyer systématiquement les caractères invisibles (`\u200b`, `\ufeff`). Si le titre extrait est vide (`""`), extraire et reformater le titre à partir du slug de la page web (`urllib.parse.unquote`).
- **Purge des mods fantômes** : Purger automatiquement de la base les références supprimées de la plateforme (ex. renvoyant *"We could not locate the item you are trying to view"*).

### 1.3 Parallélisation par sous-catégorie
- Le scraping LoversLab est organisé par sous-catégories (Clothing, WickedWhims, Objects, etc.).
- **Un worker ThreadPoolExecutor indépendant par sous-catégorie** permet de paralléliser le scraping tout en maintenant le backoff exponentiel par catégorie en cas de blocage.
- Lors de la fermeture de l'application (`ShutdownManager.trigger_shutdown()`), les workers d'arrière-plan doivent vérifier `ShutdownManager.is_shutting_down()` et quitter proprement pour éviter l'erreur *"cannot schedule new futures after interpreter shutdown"*.

### 1.4 Sous-catégories LoversLab à scraper (Sims 4 — catégorie 161)
Les sous-catégories identifiées et actives pour le scraping (IDs à intégrer) :
- 174 – WickedWhims
- 201 – Animations - WickedWhims
- 215 – Translations - WickedWhims
- 202 – Animations - Other
- 200 – Extensions
- 203 – Clothing
- 204 – Accessories & Makeup
- 205 – Body Parts
- 206 – Objects
- 404 – Paintings & Posters
- 207 – Lots
- Autres (Translations, Hairstyles, etc.)

### 1.5 Indicateur de statut du scraping dans l'UI (panneau rétractable)
- Le `CatalogView` dispose d'un panneau latéral rétractable (icône toujours visible) affichant le statut en temps réel du scraping : nombre de mods indexés, catégorie en cours, pages traitées, progression globale.
- L'icône reste visible même quand le panneau est replié pour permettre une consultation rapide du statut OK/KO.

### 1.6 Téléchargement & Résolution des Fichiers
- LoversLab propose soit des fichiers directs, soit des liens externes vers des hébergeurs tiers (Gofile, Mega, etc.). Le résolveur doit inspecter les en-têtes et le corps de la réponse.
- **Validation de l'archive avant extraction** : Toujours tester l'intégrité du fichier (`zipfile.is_zipfile(path)`) avant tentative d'extraction. Si le fichier téléchargé est une page web d'erreur ou de login (HTML), lever une exception claire et explicite.

---

## 2. Détection & Résolution des Dépendances

### 2.1 WickedWhims — détection robuste
La fonction `is_wickedwhims_name(name)` dans `src/providers/loverslab.py` gère toutes les variantes de graphie :
- Abréviations : `WW`, `ww`
- Graphies directes : `WickedWhims`, `wickedwhims`, `Wicked Whims`, `Wicked-Whims`, `Wicked_Whims`
- Typos courants : `WickedWhile`, `wicked while`, `wickedwhiles`
- Préfixes : `Sims 4 WickedWhims`, `TS4 WickedWhims`
- Suffixes de version : nettoyer `(v175)`, `[latest]`, `174h` avant comparaison
- **ID LoversLab WickedWhims** : `3169`

### 2.2 Nisa's Wicked Perversions — détection robuste
La fonction `is_nisa_name(name)` gère les variantes :
- Abréviations : `NWP`, `nwp`
- Graphies : `Nisa's Wicked Perversions`, `Nisas Wicked Perversions`, etc.
- **ID LoversLab NWP** : `29732`

> **Règle** : Un mod qui cite WickedWhims ou NWP comme prérequis doit résoudre vers leur ID LoversLab connu (`3169` / `29732`) même si le texte utilise une graphie non standard.

### 2.3 Extraction HTML des prérequis
- Avant extraction de texte, remplacer les balises `<br>`, `<p>`, `<div>`, `<li>` par des sauts de ligne `\n` (sinon les dépendances multi-lignes fusionnent en un seul candidat non parsable).
- Découper le texte par lignes pour analyser chaque candidat séparément.
- **Ignorer les DLC/extensions EA officiels** (ne sont pas des mods tiers) : filtrer les candidats contenant les mots-clés `DLC`, `Expansion Pack`, `Game Pack`, `Stuff Pack`, `Pack d'extension`, `Kit d'objets`.

### 2.4 Affichage des dépendances dans la vue détail
- La section prérequis de `ModDetailView` est **rétractable** (bouton ▲ Réduire / ▼ Développer).
- Pendant le chargement des données en ligne : afficher le message `🔄 Analyse des dépendances et prérequis...` avec un fond ardoise.
- Chaque dépendance identifiée affiche son **statut individuel** :
  - ✅ Installé
  - ⚠️ Détecté dans le catalogue (non installé)
  - ⏳ Scan en cours
  - ❌ Non détecté (scan terminé)

### 2.5 Installation partielle si dépendances introuvables
- Si toutes les dépendances sont disponibles : bouton `📦 Installer`.
- Si certaines dépendances sont introuvables dans le catalogue : bouton `⚠️ Installation Partielle` avec message d'avertissement explicite.
- L'installation **n'est pas bloquée** par les dépendances manquantes, mais l'utilisateur est informé du risque de dysfonctionnement.

---

## 3. Structure des Dossiers & Contraintes Les Sims 4

### 3.1 Profondeur des Scripts & Packages
- Les fichiers de script Python compilés (`.ts4script`) **ne doivent jamais dépasser 1 seul niveau de sous-dossier** dans `Documents/Electronic Arts/Les Sims 4/Mods`. Au-delà, le moteur du jeu ne les charge pas.
- Les fichiers de contenu (`.package`) supportent jusqu'à 5 niveaux, mais par cohérence, chaque mod doit être regroupé dans son sous-dossier unique direct.

### 3.2 Assainissement Strict des Noms de Dossiers
- Format : `{source}_{NomAssaini}_{xxx}` (ex: `loverslab_WickedWhims_1042`).
- Filtre strict : caractères alphanumériques et underscores uniquement (`[a-zA-Z0-9_]`).
- Supprimer systématiquement espaces, apostrophes, accents/diacritiques, emojis et signes de ponctuation.
- Le suffixe aléatoire `_xxx` (3 ou 4 chiffres) garantit l'absence de collision de noms de dossiers.

---

## 4. Démarrage Rapide & Tâches de Fond

### 4.1 Démarrage Inférieur à 0.5s
- Ne jamais déclencher de recherche disque exhaustive synchrone lors du lancement de l'application.
- Sauvegarder les chemins du jeu (`TS4_x64.exe`) et du répertoire `Mods` dans le cache de configuration (`AppConfig`).
- Lancer la vérification / détection de déplacement de jeu en thread démon d'arrière-plan sans impacter le thread UI principal.

### 4.2 Synchronisation Automatique de l'État Réel
- L'utilisateur peut supprimer manuellement des dossiers de mods depuis l'Explorateur Windows entre deux sessions.
- Un thread démon d'arrière-plan (`ModInstaller.start_background_installed_mods_verifier()`) vérifie l'existence des dossiers physiques et purge les entrées orphelines de la BDD SQLite.
- **Règle critique** : Ne **jamais** appeler `ModInstaller.verify_and_cleanup_installed_mods()` de manière synchrone dans un handler de route API (GET `/api/installed`, GET `/api/updates`). Ce cleanup supprime les entrées dont les dossiers n'existent pas sur disque, ce qui cause des faux-positifs en tests et des blocages en production. Le cleanup est exclusivement géré par le daemon d'arrière-plan.

### 4.3 Fermeture Propre (ShutdownManager)
- `ShutdownManager.trigger_shutdown()` est appelé dans `closeEvent` du `MainWindow`.
- Tous les workers d'arrière-plan (scraping, installation) doivent vérifier `ShutdownManager.is_shutting_down()` régulièrement et quitter leurs boucles proprement.
- Le timer de monitoring du catalogue (`catalog_view.monitor_timer`) doit être stoppé explicitement dans `closeEvent`.

---

## 5. Architecture API (FastAPI + Client REST)

### 5.1 Structure
- `src/api/routes/` : handlers FastAPI (catalog.py, installed.py, updates.py, etc.)
- `src/api/client.py` : client REST utilisé par l'UI pour appeler l'API
- `src/api/models.py` : modèles Pydantic de réponse

### 5.2 Règle de Performance (N+1)
- Toujours charger les `CatalogMod` en une seule requête et construire des dictionnaires `catalog_by_id` et `catalog_by_key (source, remote_id)` pour éviter les requêtes SQL N+1 dans les boucles.
- Lookup canonique : d'abord par `(source, remote_id)`, puis fallback par `catalog_mod_id` (avec vérification de cohérence).

### 5.3 Compteur de mods indexés (`get_catalog_mods_count`)
- La méthode `DatabaseManager.get_catalog_mods_count()` retourne le nombre de mods dans la table `catalog_mods`.
- Utilisée par `GET /api/catalog/sync-status` pour afficher le vrai compte dans l'UI (pas une valeur simulée).

---

## 6. Interface Utilisateur (UI/UX)

### 6.1 Onglet "Mes Mods" (`InstalledView`)
- Rendu sous forme de grille de tuiles modernes (`InstalledCard`) calquée sur le style du catalogue.
- Chaque tuile affiche : miniature (chargée de manière asynchrone), badge de source, nombre de fichiers (`X fichiers`), nom de dossier et date d'installation.
- **Aucun bouton ou colonne Actif / Inactif**.
- Deux actions principales :
  - `📁 Dossier` : ouverture instantanée du dossier cible dans l'Explorateur Windows.
  - `🗑️ Supprimer` : confirmation préalable puis suppression physique du dossier et suppression de l'entrée en base.
- **Signal `mods_changed`** : émis après toute suppression ou scan. Connecté dans `App` pour déclencher le rafraîchissement croisé des autres vues.

### 6.2 Onglet "Catalogue" (`CatalogView`)
- Si un mod est déjà présent sur le disque, le bouton d'installation est désactivé avec la mention `✓ Déjà Installé`.
- **Clic sur une tuile** : ouverture en plein écran de `ModDetailView` avec description complète, auteur, tags, version, lien externe et section dépendances.
- **Signal `install_finished`** : émis après toute installation réussie. Connecté dans `App` pour déclencher le rafraîchissement croisé des autres vues.

### 6.3 Onglet "Mises à Jour" (`UpdatesView`)
- **Signal `updates_applied`** : émis après application d'une ou plusieurs mises à jour. Connecté dans `App`.

### 6.4 Synchronisation Croisée des Vues (Pattern Central)
- **Toutes les mutations d'état des mods** (installation, désinstallation, mise à jour) doivent émettre un signal dans le `MainWindow` (`App`).
- `App._on_mods_state_changed()` est le handler central qui :
  1. Rafraîchit `InstalledView`
  2. Rafraîchit `UpdatesView`
  3. Rafraîchit `CatalogView`
  4. Met à jour le badge du nav bouton "Mises à Jour"
  5. Si `ModDetailView` est affiché (index 6), rafraîchit le statut d'installation du mod courant via `_refresh_current_mod_detail()`.

### 6.5 Images et Galeries dans ModDetailView
- Les images de la galerie LoversLab (screenshots du mod) doivent être chargées depuis les balises `<img>` de la section description de la page du mod.
- Les thumbnails sont chargées de manière asynchrone via `QThread` pour ne pas bloquer l'UI.

### 6.6 Journalisation Systématique
- Toute erreur de téléchargement ou d'installation doit obligatoirement être enregistrée via `logger.error(...)` afin d'être tracée à la fois en console et dans l'onglet **Logs** de l'interface.

---

## 7. Base de Données (SQLite / SQLAlchemy)

### 7.1 Modèles Principaux
- `CatalogMod` : mods indexés depuis LoversLab (et autres providers futurs).
- `InstalledMod` : mods effectivement installés sur le disque, avec lien optionnel vers `CatalogMod` via `catalog_mod_id`.
- `InstalledMod.get_requirements_mods_list()` : retourne la liste des dépendances parsée depuis `requirements_text`.

### 7.2 Champs importants de CatalogMod
- `requirements_text` : texte brut des prérequis extraits de la page LoversLab.
- `requirements_status` : état de résolution des dépendances (`NONE`, `OK`, `PARTIAL`, `MISSING`).
- `requirements_mods_json` : JSON sérialisé de la liste des dépendances résolues.

---

## 8. Tests

### 8.1 Règles de tests d'intégration
- Les tests qui créent des `InstalledMod` en base avec des `folder_name` fictifs doivent **mocker ou désactiver** le nettoyage automatique (`verify_and_cleanup_installed_mods`) pour éviter que les dossiers inexistants soient supprimés avant les assertions.
- La solution préférée est de **ne pas appeler** le cleanup dans les handlers de route (voir §4.2).

### 8.2 Structure des tests
- `tests/test_api.py` : tests d'intégration des routes principales (catalog, installed, system).
- `tests/test_enhancements.py` : tests des fonctionnalités avancées (updates, galeries, statut sync).
- `tests/test_requirements_and_details.py` : tests unitaires de la détection WickedWhims/NWP et de l'extraction des prérequis.

### 8.3 Vérification obligatoire après chaque modification
```bash
uv run ruff check src/ tests/
uv run pytest tests/ -q
```
Les deux commandes doivent passer à 0 erreur avant tout commit.
