# SIMS 4 Mods Manager 💎

Application de bureau moderne et complète conçue en Python (PySide6) pour centraliser, télécharger, organiser, activer/désactiver et mettre à jour les mods pour **Les Sims 4**.

---

## 📋 Prérequis

1. **Python** (version 3.11 à 3.13 recommandée)
2. **uv** (Gestionnaire de paquets ultra-rapide) :
   ```powershell
   # Si uv n'est pas installé (via Scoop ou installateur officiel)
   scoop install uv
   ```
3. **Navigateur Playwright (Chromium)** :
   Nécessaire pour l'authentification automatique, le contournement des protections anti-bot (Cloudflare Turnstile) et la validation du consentement adulte (+18 ans) sur les sites de mods.
   ```powershell
   uv run playwright install chromium
   ```
   *(Note : Si vous disposez déjà de Microsoft Edge ou Google Chrome sur votre système Windows, l'application est également capable de s'appuyer dessus automatiquement).*

---

## 🚀 Installation & Démarrage Rapide

### 1. Installation des dépendances du projet
```powershell
uv sync
```

### 2. Installation des composants de navigation (Anti-Bot)
```powershell
uv run playwright install chromium
```

### 3. Lancement de l'application
```powershell
uv run python run.py
```

### 4. Exécution des tests unitaires
```powershell
uv run pytest
```

---

## 🌟 Fonctionnalités Principales

- 🌐 **Comptes, Sessions & Anti-Bot (Page d'accueil par défaut)** :
  - Connexion manuelle / interactive à **LoversLab** et **Patreon** avec un profil Chromium persistant sans double fenêtre.
  - Validation automatique du consentement adulte et mémorisation des cookies de session.
- 📁 **Catalogue Multi-Sources Unifié** :
  - Scraping multi-pages configurable (1, 2, 5, 10, 20 pages) depuis LoversLab (Catégorie 161 - The Sims 4).
  - Téléchargement et mise en cache asynchrone des miniatures pour un affichage instantané et fluide.
  - Filtres multi-critères : recherche texte, sources, statuts d'accès Patreon (Public, Abonné, Verrouillé), état d'installation, tri par date/nom.
- 🔓 **Vérification Intelligente Patreon** :
  - Détection automatique des paliers requis et des posts débloqués par votre abonnement.
- 💾 **Détection Multi-Langue & Installation Robuste** :
  - Détection automatique des répertoires `Mods` (gérant les espaces insécables `\xa0` des installations françaises, anglaises, allemandes, espagnoles, etc.).
  - Respect strict de la profondeur maximale de 1 sous-dossier pour les fichiers `.ts4script`.
  - Prise en charge des archives `.zip`, `.rar`, et `.7z`.
- ⚡ **Gestion de Versions & Mises à Jour en 1 Clic** :
  - Comparaison automatique des dates de publication.
  - Sauvegarde automatique (`.zip`) dans `~/.sims4_mod_manager/backups/` avant tout écrasement.
- 📋 **Journaux & Logs en Direct** :
  - Visualisation en temps réel de tous les événements d'exécution (avec coloration syntaxique).
  - Bouton **📋 Copier Tout** pour un partage et débogage immédiat.
- 🎛️ **Gestion des Mods & Lanceur de Jeu** :
  - Activation / Désactivation instantanée sans suppression de fichiers (`.disabled`).
  - Lanceur direct pour démarrer Les Sims 4.

---

## 📂 Structure du Projet

```
SIMS4-Mods-Manager/
├── pyproject.toml              # Configuration des dépendances uv
├── run.py                      # Point d'entrée principal avec contrôle Playwright
├── src/
│   ├── core/
│   │   ├── config.py           # Configuration globale & chemins d'accès
│   │   ├── database.py         # Modèles SQLite (CatalogMod, InstalledMod, AccountSession)
│   │   ├── game_detector.py    # Détection du jeu multi-langues & registre
│   │   ├── mod_installer.py    # Extraction, profondeur ts4script & sauvegardes
│   │   ├── mod_toggle.py       # Activation / désactivation (.disabled)
│   │   └── session_manager.py  # Gestion Playwright & client HTTP rapide curl_cffi
│   ├── providers/
│   │   ├── base.py             # Interface BaseSourceProvider
│   │   ├── loverslab.py        # Scraper LoversLab avec support lazy loading images
│   │   └── patreon.py          # Analyseur des accès et pièces jointes Patreon
│   ├── ui/
│   │   ├── app.py              # Fenêtre principale & gestion des 6 vues
│   │   ├── theme.py            # Stylesheet QSS moderne Dark
│   │   ├── components/         # ModCard (async thumb), FilterBar, Badges
│   │   └── views/              # Comptes (Index 0), Catalogue, Installés, MàJ, Logs, Paramètres
│   └── utils/
│       ├── archive.py          # Gestion des archives (.zip, .rar, .7z)
│       ├── logger.py           # Logger avec émetteur Qt en temps réel
│       └── resource_cfg.py     # Configuration Resource.cfg
└── tests/                      # Suite de tests unitaires
```
