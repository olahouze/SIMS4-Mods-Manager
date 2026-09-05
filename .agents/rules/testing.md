# Directives de Tests Unitaires et Exécution Terminal

## RÈGLES CRITIQUES D'EXÉCUTION DES TESTS (WINDOWS & WORKSPACE)

1. **Exécution Élément par Élément (Obligatoire)** :
   - Ne **JAMAIS** lancer la commande globale `pytest tests/` ou `pytest tests/ -v`. Sur cette machine Windows, l'exécution globale en un seul bloc provoque des blocages complets et des freezes de processus.
   - Toujours exécuter les tests dossier par dossier (module par module) ou fichier par fichier :
     - `.venv\Scripts\pytest tests/utils -v`
     - `.venv\Scripts\pytest tests/database -v`
     - `.venv\Scripts\pytest tests/api -v`
     - `.venv\Scripts\pytest tests/providers -v`
     - `.venv\Scripts\pytest tests/ui -v`
     - `.venv\Scripts\pytest tests/services -v`

2. **Terminal Visible et Synchrone (Zéro Background Tasks)** :
   - Ne **JAMAIS** exécuter de tests en tâche de fond (`manage_task` / background task).
   - Toujours utiliser `run_command` avec `WaitMsBeforeAsync: 10000` afin que la commande s'exécute de façon synchrone et affiche son résultat immédiatement et visiblement.
   - Ne jamais utiliser le mode silencieux (`-q`), toujours le mode verbeux (`-v`).

3. **Zéro Warning & Zéro Appel Réseau Réel** :
   - Tous les tests doivent s'exécuter avec 0 avertissement (0 warning).
   - Tous les appels HTTP distants vers des sites web réels (LoversLab, Patreon, Cloudflare) sont strictement interdits dans les tests et doivent être mockés via des fixtures HTML ou des réponses mockées.
