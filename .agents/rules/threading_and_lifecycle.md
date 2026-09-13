# Démarrage, Threads & Cycle de Vie Applicatif

## 1. Démarrage Réactif (< 0.5s)
- Ne jamais lancer de recherche disque exhaustive synchrone lors de l'initialisation de l'application ou du serveur API.
- Les chemins du jeu (`TS4_x64.exe`) et du dossier `Mods` sont persistés dans la configuration (`AppConfig`) et vérifiés de façon asynchrone sans geler l'interface.

---

## 2. Détection de l'État Réel (Daemon Worker Asynchrone)
- Un thread démon d'arrière-plan (`ModInstallerService.start_background_installed_mods_verifier()`) surveille les modifications externes de l'Explorateur Windows et purge les entrées orphelines.
- **Règle absolue** : Ne **jamais** appeler `verify_and_cleanup_installed_mods()` de manière synchrone dans un handler de route API (comme `GET /api/installed` ou `GET /api/updates`). Ce cleanup synchrone détruit les entrées de test et pénalise lourdement la latence HTTP.

---

## 3. Fermeture Propre (`ShutdownManager`)
- Le signal de fermeture est déclenché via `ShutdownManager.trigger_shutdown()` lors du `closeEvent` de PySide6 ou de l'arrêt du processus.
- Tous les workers, timers et pools de threads d'arrière-plan doivent interroger `ShutdownManager.is_shutting_down()` et s'interrompre proprement pour éviter tout blocage ou exception à la fermeture de l'interpréteur Python.
