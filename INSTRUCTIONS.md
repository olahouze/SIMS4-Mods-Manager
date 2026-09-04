# Instructions du Projet : Sims 4 Mods Manager

Ce document consigne les règles d'architecture, les contraintes techniques et les apprentissages clés acquis sur le projet pour guider les développements futurs.

---

## 1. Scraping & Intégration LoversLab

1. **Authentification & Session Cloudflare** :
   - L'authentification passe par un navigateur Playwright afin de résoudre les défis Cloudflare et d'extraire les cookies de session (`cf_clearance`, `ips4_IPSSessionFront`).
   - Toutes les requêtes HTTP suivantes doivent impérativement réutiliser ces cookies ainsi que le `User-Agent` du navigateur sous peine de blocage 403.

2. **Scraping Incrémental du Catalogue** :
   - Le scraping des pages du catalogue s'exécute en tâche de fond.
   - La première page doit être analysée, persistée en BDD et affichée immédiatement pour un rendu sans latence.
   - En cas d'erreur de requête sur les pages suivantes, appliquer un délai d'attente exponentiel (backoff) avant nouvel essai pour éviter le bannissement d'IP.
   - **Nettoyage des titres** : Nettoyer systématiquement les caractères invisibles (`\u200b`, `\ufeff`). Si le titre extrait est vide (`""`), extraire et reformater le titre à partir du slug de la page web (`urllib.parse.unquote`).
   - **Purge des mods fantômes** : Purger automatiquement de la base les références supprimées de la plateforme (ex. renvoyant *"We could not locate the item you are trying to view"*).

3. **Téléchargement & Résolution des Fichiers** :
   - LoversLab propose soit des fichiers directs, soit des liens externes vers des hébergeurs tiers (Gofile, Mega, etc.). Le résolveur doit inspecter les en-têtes et le corps de la réponse.
   - **Validation de l'archive avant extraction** : Toujours tester l'intégrité du fichier (ex. `zipfile.is_zipfile(path)`) avant tentative d'extraction. Si le fichier téléchargé est une page web d'erreur ou de login (HTML), lever une exception claire et explicite.

---

## 2. Structure des Dossiers & Contraintes Les Sims 4

1. **Profondeur des Scripts & Packages** :
   - Les fichiers de script Python compilés (`.ts4script`) **ne doivent jamais dépasser 1 seul niveau de sous-dossier** dans `Documents/Electronic Arts/Les Sims 4/Mods`. Au-delà, le moteur du jeu ne les charge pas.
   - Les fichiers de contenu (`.package`) supportent jusqu'à 5 niveaux, mais par cohérence, chaque mod doit être regroupé dans son sous-dossier unique direct.

2. **Assainissement Strict des Noms de Dossiers** :
   - Format de dossier : `{source}_{NomAssaini}_{xxx}` (ex: `loverslab_WickedWhims_1042`).
   - Filtre strict : caractères alphanumériques et underscores uniquement (`[a-zA-Z0-9_]`).
   - Supprimer systématiquement espaces, apostrophes, accents/diacritiques, emojis et signes de ponctuation.
   - Le suffixe aléatoire `_xxx` (3 ou 4 chiffres) garantit l'absence de collision de noms de dossiers.

---

## 3. Démarrage Rapide & Tâches de Fond

1. **Démarrage Inférieur à 0.5s** :
   - Ne jamais déclencher de recherche disque exhaustive synchrone lors du lancement de l'application.
   - Sauvegarder les chemins du jeu (`TS4_x64.exe`) et du répertoire `Mods` dans le cache de configuration (`AppConfig`).
   - Lancer la vérification / détection de déplacement de jeu en thread démon d'arrière-plan sans impacter le thread UI principal.

2. **Synchronisation Automatique de l'État Réel** :
   - L'utilisateur peut supprimer manuellement des dossiers de mods depuis l'Explorateur Windows entre deux sessions.
   - Un thread démon d'arrière-plan (`ModInstaller.start_background_installed_mods_verifier()`) vérifie l'existence des dossiers physiques et purge les entrées orphelines de la BDD SQLite.

---

## 4. Règles d'Interface Utilisateur (UI/UX) & Journalisation

1. **Onglet "Mes Mods"** :
   - Rendu sous forme de grille de tuiles modernes (`InstalledCard`) calquée sur le style du catalogue.
   - Chaque tuile affiche : miniature (chargée de manière asynchrone), badge de source, nombre de fichiers (`X fichiers`), nom de dossier et date d'installation.
   - **Aucun bouton ou colonne Actif / Inactif**.
   - Deux actions principales :
     - `📁 Dossier` : ouverture instantanée du dossier cible dans l'Explorateur Windows.
     - `🗑️ Supprimer` : confirmation préalable puis suppression physique du dossier et suppression de l'entrée en base.

2. **Onglet "Catalogue"** :
   - Si un mod est déjà présent sur le disque, le bouton d'installation est désactivé avec la mention `✓ Déjà Installé`.
   - **Clic sur une tuile** : ouverture en surimpression d'une fenêtre modale (`ModDetailModal`) contenant la description complète de la page web, l'auteur, les tags, la version, un lien externe et une fermeture facile (`✕`, bouton Fermer ou touche `Échap`).

3. **Journalisation Systématique** :
   - Toute erreur de téléchargement ou d'installation doit obligatoirement être enregistrée via `logger.error(...)` afin d'être tracée à la fois en console et dans l'onglet **Logs** de l'interface.
