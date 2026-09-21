# Classification des Dépendances, Filtrage du Bruit & Surcharge Utilisateur

Ce document décrit le fonctionnement du moteur d'extraction, de filtrage heuristique et de résolution des dépendances de **SIMS 4 Mods Manager**.

---

## 1. Vue d'ensemble

Lorsqu'un mod est extrait depuis LoversLab ou Patreon, la section **Requirements** / **Prérequis** contient fréquemment :
1. De vrais mods Sims 4 indispensables ou complémentaires (ex: *WickedWhims*, *Nisa's Wicked Perversions*, *Lot 51 Core Library*).
2. Des DLCs ou packs officiels du jeu Sims 4 (ex: *Chiens et Chats*, *Saisons*, *Heure de gloire*).
3. Des consignes techniques de configuration du jeu (ex: *"Script Mods enabled in Game Options"*).
4. Des disclaimers d'auteurs (ex: *"No third-party library or framework is required"*).
5. Des phrases narratives ou de description du mod.

Pour garantir une expérience utilisateur fluide et éviter de bloquer des installations à cause de faux positifs, l'application combine **3 couches de traitement** :
- **Couche 1 : Filtrage heuristique automatique (`dependency_noise_rules.py`)** éliminant le bruit évident dès l'extraction.
- **Couche 2 : Contrôle & Surcharge utilisateur (`requirements_overrides`)** permettant à l'utilisateur de requalifier manuellement n'importe quel élément en `MOD` ou `COMMENT`.
- **Couche 3 : Installation tolérante aux dépendances (`allow_partial=True`)** permettant d'installer le mod principal même si certaines dépendances sont introuvables.

---

## 2. Tableau Centralisé des Motifs de Commentaires & Faux Positifs

Le module [`src/application/dependencies/dependency_noise_rules.py`](file:///d:/Workspace/Github/OLAHOUZE/SIMS4-Mods-Manager/src/application/dependencies/dependency_noise_rules.py) regroupe les motifs et expressions courantes reconnus comme des commentaires ou du bruit :

| Catégorie | Exemples de motifs reconnus | Action du Moteur |
| :--- | :--- | :--- |
| **Options et Configuration du Jeu** | `Game Options`, `Script Mods Allowed`, `Script Mods Enabled`, `Custom Content`, `Restart the game`, `Redémarrer le jeu` | Ignoré à l'extraction / Classé en `COMMENT_NOISE` |
| **Disclaimers d'absence de mod** | `No third-party library or framework is required`, `No .package file is required`, `Script-only mod`, `does not add tuning`, `Not required:`, `Pas requis` | Ignoré à l'extraction / Classé en `COMMENT_NOISE` |
| **Consignes de versions & patchs** | `The Sims 4 build 1.125.59 (Patch actual)`, `Tested on 1.125.59`, `Current compatible version`, `Latest patch` | Si ce n'est pas un DLC officiel, filtré pour éviter de chercher un mod inexistant |
| **Phrases narratives / Prose** | `EA gives you Flirty...`, `The save remembers...`, `Bad decisions. Better stories`, `If you only install...`, `You are missing the gameplay ecosystem` | Détecté par analyse de structure (longueur > 55 car., ponctuation de dialogue, verbes conjugués) et éliminé |
| **Navigation & Chemins** | `Game Options → Other → Script Mods Allowed`, `Menu -> Options` | Rejeté en tant qu'instruction de navigation |

---

## 3. Surcharge Utilisateur (`requirements_overrides`)

Bien que le filtrage automatique couvre la majorité des cas, l'utilisateur a le contrôle final dans l'interface :

1. Dans la boîte de dialogue des détails du mod ou de gestion des dépendances, chaque ligne de prérequis peut être basculée entre :
   - **`MOD`** : L'utilisateur confirme qu'il s'agit d'un vrai mod attendu. Même si le titre ressemble à une consigne, le système cherchera à le résoudre dans le catalogue.
   - **`COMMENT`** : L'utilisateur indique qu'il s'agit d'un commentaire d'auteur, d'une note ou d'un conseil. L'élément est immédiatement marqué `COMMENT_NOISE` et ne bloque plus le statut du mod.
2. Les choix sont persistés dans la colonne `requirements_overrides_json` de la table `catalog_mods` sous la forme d'un dictionnaire `{ "titre_du_prérequis": "MOD" | "COMMENT" }`.

---

## 4. Gestion des Installations Partielles (`allow_partial`)

Lors de l'installation d'un mod via l'API REST (`POST /api/catalog/install`) :
- **Paramètre `allow_partial`** (valeur par défaut : `True`) :
  - Si une dépendance requise n'a pas pu être trouvée dans le catalogue distant ou si son téléchargement échoue (ex: mod archivé, lien Patreon payant), l'orchestrateur **ne fait pas échouer l'installation du mod principal**.
  - Le mod principal est téléchargé et déployé normalement dans le dossier `Mods/`.
  - La réponse API indique un succès partiel :
    `"Installation partielle réussie ! Le mod 'Nom' a été installé avec succès, mais X dépendance(s) introuvable(s) (...) n'ont pas pu être ajoutées."`
- **Dans le script de test [`scripts/simulate_user_flow.py`](file:///d:/Workspace/Github/OLAHOUZE/SIMS4-Mods-Manager/scripts/simulate_user_flow.py)** :
  - Le script active explicitement `allow_partial=True`.
  - Le rapport d'exécution comptabilise distinctement les installations complètes (`✅ Succès`) et partielles (`⚠️ Succès partiel`).
  - Tous les mods installés en mode partiel sont tracés et nettoyés lors de la phase de désinstallation post-test.
