# Directives de Tests Unitaires & Validation (Green State)

## 1. Règle de Validation Obligatoire (Green State)
Avant chaque commit ou validation de tâche, les vérifications suivantes doivent être exécutées avec succès (100% succès, 0 erreur, 0 warning) :

```bash
# 1. Analyse statique et linter (doit retourner 0 erreur)
uv run ruff check src/ tests/

# 2. Exécution des tests ÉLÉMENT PAR ÉLÉMENT en terminal visible (JAMAIS la suite globale d'un bloc ni en background)
uv run pytest tests/core -v
uv run pytest tests/utils -v
uv run pytest tests/database -v
uv run pytest tests/api -v
uv run pytest tests/providers -v
uv run pytest tests/ui -v
uv run pytest tests/services -v
```

---

## 2. RÈGLES CRITIQUES D'EXÉCUTION DES TESTS (WINDOWS & WORKSPACE)

1. **Exécution Élément par Élément (Obligatoire)** :
   - Ne **JAMAIS** lancer la commande globale `pytest tests/` ou `pytest tests/ -v`. Sur cette machine Windows, l'exécution globale en un seul bloc provoque des blocages complets et des freezes de processus.
   - Toujours exécuter les tests dossier par dossier (module par module) ou fichier par fichier.

2. **Terminal Visible et Synchrone (Zéro Background Tasks)** :
   - Ne **JAMAIS** exécuter de tests en tâche de fond (`manage_task` / background task silencieuse).
   - Toujours utiliser `run_command` avec un timeout suffisant (`WaitMsBeforeAsync: 10000`) afin que la commande s'exécute de façon synchrone et affiche son résultat immédiatement et visiblement.
   - Ne jamais utiliser le mode silencieux (`-q`), toujours le mode verbeux (`-v`).

3. **Zéro Warning & Zéro Appel Réseau Réel** :
   - Tous les tests doivent s'exécuter avec 0 avertissement (0 warning).
   - Tous les appels HTTP distants vers des sites web réels (LoversLab, Patreon, Cloudflare) sont strictement interdits dans les tests et doivent être mockés via des fixtures HTML ou des réponses mockées.

---

## 3. Isolation Stricte de la Base de Données de Test
- Les tests automatisés ne doivent **jamais** polluer ni modifier la base de données réelle de l'utilisateur (`sims4_mods.db`).
- `src/core/config.py` lit la variable d'environnement `SIMS4_DB_PATH`.
- `tests/conftest.py` configure une fixture de session `isolate_test_database` créant une base temporaire dédiée pour toute la durée des tests, garantissant une étanchéité totale avec l'environnement utilisateur.
