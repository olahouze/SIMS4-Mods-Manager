# Scripts d'Automatisation et de Simulation - SIMS 4 Mods Manager

Ce dossier regroupe les scripts utilitaires d'automatisation, de diagnostic et de simulation de bout en bout pour le projet **SIMS 4 Mods Manager**.

---

## 📄 `simulate_user_flow.py`

Le script [`simulate_user_flow.py`](simulate_user_flow.py) simule les actions complètes d'un utilisateur en interagissant directement avec l'**API REST FastAPI** de l'application et en effectuant un **audit de cohérence en direct sur Internet**.

### 🚀 Fonctionnalités principales

1. **Gestion automatique du serveur API (Étape 0)** :
   - Vérifie si l'API REST est déjà active (sur `http://127.0.0.1:8000` par défaut).
   - Si elle est absente, lance automatiquement en arrière-plan `python run.py --server --port 8000` via l'environnement virtuel du projet.
   - À la fin de la simulation, le processus serveur est arrêté proprement.

2. **Gestion autonome de la session LoversLab & Anti-bot (Étape 1)** :
   - Tente d'abord de récupérer les cookies de session existants dans la base SQLite locale.
   - Si la session est manquante, expirée ou si l'option `--force-login` est spécifiée, lance le navigateur **Playwright Chromium/Edge** intégré pour permettre la connexion ou le franchissement de la protection Cloudflare.
   - Prépare une session HTTP autonome (`curl_cffi` avec émulation de navigateur Chrome) pour auditer le web sans être bloqué.

3. **Synchronisation du catalogue LoversLab (Étape 2)** :
   - Déclenche le scraping via `POST /api/catalog/sync` avec le nombre de pages paramétré.
   - Suit la progression en direct (pourcentage, nombre de pages complétées, mods répertoriés) jusqu'à achèvement.

4. **Audit de cohérence Internet autonome (Étape 3)** :
   - Parcourt exhaustivement tous les mods du catalogue via l'API (`GET /api/catalog`).
   - Teste en direct chaque mod sur le Web :
     - **Accessibilité de la page** : Détection des erreurs HTTP 404, 410 ou pages supprimées.
     - **Téléchargement direct LoversLab** : Test de la requête `/?do=download` pour vérifier qu'elle délivre bien le fichier ou la sélection attendue (détection des erreurs 403, 404 ou redirections anormales).
     - **Cohérence Patreon** : Vérifie la cohérence entre le statut enregistré (`PUBLIC`, `UNLOCKED`, `LOCKED`) et l'accès réel sur Patreon.
     - **Validité des liens externes** : Contrôle des liens d'hébergement externes (Mega, Mediafire, Simfileshare, Google Drive...).
   - **Règle stricte** : Seules les **incohérences avérées** sont consignées (aucun bruit pour les mods conformes).

5. **Installation séquentielle des mods installables (Étape 4)** :
   - Détecte les mods LoversLab directement installables et les installe séquentiellement via `POST /api/catalog/install` (`install_dependencies=True`).
   - Journalise le temps d'exécution, le statut de succès/échec et les dépendances installées.

6. **Filtrage sélectif des logs & Rapport final (Étape 5)** :
   - Parcours séquentiel exhaustif du fichier `app.log` et du buffer API.
   - **Filtrage strict** : Élimination absolue des lignes d'information (`[INFO]`) et de débogage (`[DEBUG]`). Seules les erreurs réelles (`[ERROR]`, `[CRITICAL]` et traces de pile d'exceptions Python) sont conservées.
   - Génération d'un rapport Markdown horodaté dans le sous-dossier `scripts/rapports/`.
   - Affichage immédiat du chemin absolu du rapport dans la console.

---

## 🛠️ Utilisation

Les commandes doivent être exécutées avec l'environnement virtuel du projet (via `uv run` ou directement avec le python du `.venv`) :

### Syntaxe générale

```bash
uv run python scripts/simulate_user_flow.py [OPTIONS]
```

### Options disponibles

| Option | Type | Description | Défaut |
| :--- | :--- | :--- | :--- |
| `--api-url` | `str` | URL racine de l'API REST de l'application | `http://127.0.0.1:8000` |
| `--max-pages` | `int` | Nombre de pages LoversLab à scraper par catégorie (`0` pour toutes) | `1` |
| `--full` | *drapeau* | Raccourci pour scraper l'intégralité du site LoversLab (`--max-pages 0`) | `False` |
| `--max-installs` | `int` | Nombre maximal de mods installables à installer séquentiellement | `None` (tous) |
| `--skip-install` | *drapeau* | Exécute uniquement le scraping et l'audit web, sans modifier le dossier du jeu | `False` |
| `--force-login` | *drapeau* | Force l'ouverture du navigateur pour réauthentifier LoversLab | `False` |

---

## 💡 Exemples pratiques

### 1. Test rapide (Scraping 1 page + Audit, sans installation dans le jeu)
Idéal pour valider rapidement le bon fonctionnement sans toucher aux fichiers Sims 4 :
```bash
uv run python scripts/simulate_user_flow.py --max-pages 1 --skip-install
```

### 2. Test complet léger (Scraping 1 page + 1 installation)
```bash
uv run python scripts/simulate_user_flow.py --max-pages 1 --max-installs 1
```

### 3. Simulation avec réauthentification LoversLab forcée
Ouvre le navigateur Playwright pour valider le captcha ou se connecter avant de lancer l'audit :
```bash
uv run python scripts/simulate_user_flow.py --force-login --max-pages 1 --skip-install
```

### 4. Audit complet exhaustif du catalogue
Scrape toutes les pages LoversLab et audite chaque mod :
```bash
uv run python scripts/simulate_user_flow.py --full --skip-install
```

---

## 📊 Rapports générés (`scripts/rapports/`)

Les rapports sont automatiquement créés dans le dossier `scripts/rapports/` au format Markdown horodaté :
`scripts/rapports/simulation_rapport_YYYYMMDD_HHMMSS.md`

Ce dossier est ignoré par Git via le fichier `.gitignore`.

### Structure d'un rapport généré :
1. **Synthèse globale** : Tableau récapitulatif chiffré (nombre de mods audités, nombre d'incohérences, succès/échecs d'installation, erreurs recensées).
2. **Incohérences détectées sur Internet** : Tableau détaillé listant uniquement les anomalies constatées (Titre, URL, Statut dans l'application, Résultat Internet réel, Explication).
3. **Résultats des installations séquentielles** : Durée, statut, message et dépendances installées pour chaque mod.
4. **Erreurs d'application relevées** : Bloc textuel contenant l'ensemble des erreurs `[ERROR]`, `[CRITICAL]` et exceptions survenues lors de la session (sans aucun bruit `[INFO]` ni `[DEBUG]`).
