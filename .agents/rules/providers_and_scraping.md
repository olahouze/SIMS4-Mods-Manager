# Fournisseurs de Mods & Intégrations de Scraping

## 1. LoversLab : Authentification & Session Cloudflare
- L'authentification passe par un navigateur Playwright afin de résoudre les défis Cloudflare et d'extraire les cookies de session (`cf_clearance`, `ips4_IPSSessionFront`, `ips4_member_id`, `ips4_hasAcceptedAge`).
- Toutes les requêtes HTTP suivantes doivent impérativement réutiliser ces cookies ainsi que le `User-Agent` du navigateur via `SessionManager.get_http_session("loverslab")` sous peine de blocage HTTP 403 / 503.

---

## 2. Scraping Incrémental du Catalogue
- Le scraping s'exécute en tâche de fond de manière non bloquante.
- **Affichage instantané** : La première page doit être analysée, persistée en base de données et émise immédiatement pour un rendu fluide dès le lancement.
- **Backoff exponentiel** : En cas d'erreur de requête sur les pages suivantes, appliquer un délai d'attente exponentiel avant nouvel essai pour éviter le bannissement d'IP.
- **Nettoyage des titres** : Nettoyer systématiquement les caractères invisibles (`\u200b`, `\ufeff`). Si le titre extrait est vide (`""`), extraire et reformater le titre à partir du slug de l'URL (`urllib.parse.unquote`).
- **Purge des mods fantômes** : Purger automatiquement de la base les références supprimées de la plateforme (ex. *"We could not locate the item you are trying to view"*).

---

## 3. Parallélisation par Sous-Catégorie & Concurrence
- Le scraping LoversLab est organisé par sous-catégories (174: WickedWhims, 201: Animations, 203: Clothing, etc.).
- **Worker ThreadPoolExecutor indépendant par sous-catégorie** : Permet de paralléliser le scraping tout en maintenant le backoff exponentiel par catégorie.
- **Arrêt propre** : Lors de l'arrêt de l'application (`ShutdownManager.trigger_shutdown()`), les workers d'arrière-plan doivent vérifier `ShutdownManager.is_shutting_down()` et s'interrompre proprement pour éviter l'erreur *"cannot schedule new futures after interpreter shutdown"*.

---

## 4. Téléchargement & Validation des Fichiers
- LoversLab propose soit des fichiers hébergés en direct, soit des liens externes (Gofile, Mega, etc.). Le résolveur inspecte les en-têtes et le corps de la réponse.
- **Validation impérative de l'archive** : Toujours tester l'intégrité du fichier (`zipfile.is_zipfile(path)`) avant tentative d'extraction. Si le fichier téléchargé est une page web d'erreur ou de login (HTML), lever une exception claire et explicite.

---

## 5. Provider Patreon
- Architecture modulaire calquée sur LoversLab : `client.py` (requêtes HTTP / API Patreon), `parser.py` (posts et pièces jointes), `provider.py` (façade métier implémentant le contrat de synchronisation et téléchargement de `BaseSourceProvider`).
