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
| `--max-pages` | `int` | Nombre de pages LoversLab à scraper par catégorie (`-1` pour toutes) | `-1` (toutes) |
| `--full` | *drapeau* | Raccourci pour scraper l'intégralité du site LoversLab (`--max-pages -1`) | `False` |
| `--max-installs` | `int` | Nombre maximal de mods installables à installer séquentiellement (`-1` pour tous) | `-1` (tous) |
| `--skip-install` | *drapeau* | Exécute uniquement le scraping et l'audit web, sans modifier le dossier du jeu | `False` |
| `--skip-sync` | *drapeau* | Réutilise le catalogue local existant sans relancer le scraping LoversLab (gain de temps majeur) | `False` |
| `--force-login` | *drapeau* | Force l'ouverture du navigateur pour réauthentifier LoversLab | `False` |
| `--keep-installed` | *drapeau* | Conserve les mods installés sans les désinstaller automatiquement à la fin | `False` |
| `--concurrency` | `int` | Nombre de threads concurrents pour accélérer l'audit web | `4` |
| `--limit-audit` | `int` | Nombre maximal de mods à auditer sur Internet (`-1` pour tous, échantillon de test) | `-1` (tous) |
| `--fail-on-errors` | *drapeau* | Retourne un exit code `1` si des installations échouent ou en cas d'erreurs critiques (CI/CD) | `False` |
| `--clean-only` | *drapeau* | Désinstalle immédiatement les mods de test LoversLab restés dans le jeu sans relancer la simulation | `False` |

---

## 💡 Exemples pratiques

### 1. Nettoyage immédiat des mods de test résiduels
Permet de purger les mods de test restés dans le jeu suite à une simulation antérieure :
```bash
uv run python scripts/simulate_user_flow.py --clean-only
```

### 2. Exécution par défaut (Intégrale : toutes les pages & tous les mods installables)
Par défaut, le script scrape toutes les pages (`--max-pages -1`) et installe tous les mods installables (`--max-installs -1`) avant de les nettoyer automatiquement :
```bash
uv run python scripts/simulate_user_flow.py
```

### 3. Test rapide restreint (Scraping 1 page + Audit limité à 5 mods, sans installation)
Idéal pour valider rapidement le bon fonctionnement sans toucher aux fichiers Sims 4 :
```bash
uv run python scripts/simulate_user_flow.py --max-pages 1 --limit-audit 5 --skip-install
```

### 4. Test complet ciblé avec parallélisme accru (1 page + 1 installation)
```bash
uv run python scripts/simulate_user_flow.py --max-pages 1 --max-installs 1 --concurrency 6
```

### 5. Exécution CI/CD avec code de retour strict
```bash
uv run python scripts/simulate_user_flow.py --max-pages 1 --max-installs 2 --fail-on-errors
```

### 6. Simulation avec réauthentification LoversLab forcée
Ouvre le navigateur Playwright pour valider le captcha ou se connecter avant de lancer l'audit :
```bash
uv run python scripts/simulate_user_flow.py --force-login --max-pages 1 --skip-install
```

---

## 📊 Rapports générés (`scripts/rapports/`)

Les rapports sont automatiquement créés dans le dossier `scripts/rapports/` sous **deux formats complémentaires** horodatés :
1. **Format Markdown** : `scripts/rapports/simulation_rapport_YYYYMMDD_HHMMSS.md`
2. **Format JSON structuré** : `scripts/rapports/simulation_rapport_YYYYMMDD_HHMMSS.json`

Ce dossier est ignoré par Git via le fichier `.gitignore`.

### Structure d'un rapport généré :
1. **Synthèse globale** : Tableau récapitulatif chiffré (nombre de mods audités, nombre d'incohérences, succès/échecs d'installation, erreurs recensées).
2. **Incohérences détectées sur Internet** : Tableau détaillé listant uniquement les anomalies constatées (Titre, URL, Statut dans l'application, Résultat Internet réel, Explication).
3. **Résultats des installations séquentielles** : Durée, statut, message et dépendances installées pour chaque mod.
4. **Erreurs d'application relevées** : Bloc textuel contenant l'ensemble des erreurs `[ERROR]`, `[CRITICAL]` et exceptions survenues lors de la session (sans aucun bruit `[INFO]` ni `[DEBUG]`).
5. **Rapport JSON** : Structure clé-valeur (`metadata`, `stats`, `inconsistencies`, `installation_results`, `cleanup_results`, `filtered_errors`) facilement exploitable par des scripts tiers ou des outils de visualisation.
