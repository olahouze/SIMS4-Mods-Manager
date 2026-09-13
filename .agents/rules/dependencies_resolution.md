# Détection & Résolution des Dépendances

## 1. Table de Correspondance & Détection Découplée
- **Table `SPECIAL_DEPENDENCY_CASES`** : Dans `src/services/dependency_resolver.py`, aucune valeur n'est codée en dur dans les branches du code. Une table de correspondance centralise les cas spécifiques.
- **WickedWhims (ID `3169`)** : Actuellement le seul cas spécifique de la table, défini avec son URL canonique (`https://www.loverslab.com/files/file/3169-wickedwhims/`) et sa liste d'alias exhaustifs (`WW`, `ww`, avec/sans tirets ou underscores : `Wicked-Whims`, `wicked_whims`, `Wicked Whims`...).
- **Traitement standardisé** : Nisa's Wicked Perversions et tous les autres mods sont traités de façon homogène via la recherche automatique dans le catalogue BDD ou via `ModMatcher`.

---

## 2. Extraction HTML & Filtrage DLC EA
- Avant extraction de texte, remplacer les balises de bloc (`<br>`, `<p>`, `<div>`, `<li>`) par `\n` pour préserver les listes distinctes.
- **Filtrage des packs officiels EA** : Utiliser `GameDlcMatcher` pour identifier et séparer automatiquement les mentions de `DLC`, `Expansion Pack`, `Game Pack`, `Stuff Pack`, `Kit d'objets` qui ne sont pas des mods tiers communautaires.

---

## 3. Statuts et Cycle de Vie des Dépendances
Chaque élément de dépendance (`DependencyItem`) est résolu avec un statut unifié :
- `INSTALLED` : Installé localement dans le répertoire Mods des Sims 4.
- `DETECTED_NOT_INSTALLED` : Répertorié dans le catalogue distant ou les cas spécifiques, prêt à être téléchargé.
- `NOT_DETECTED_SCANNING` : Non trouvé pour le moment, mais une synchronisation du catalogue est en cours.
- `NOT_DETECTED_FINISHED` : Non identifié / absent du catalogue après synchronisation complète.
- `GAME_DLC` : Pack de jeu officiel Les Sims 4 (détecté ou à vérifier dans les fichiers du jeu).

---

## 4. Politique d'Installation Partielle
- Si des dépendances sont non trouvées (`unfound` / `NOT_DETECTED_FINISHED`), l'installation n'est jamais bloquée arbitrairement.
- L'utilisateur a accès au dialogue `DependenciesDialog` avec le bouton `⚠️ Installation Partielle`, l'informant explicitement des risques tout en lui laissant le contrôle.
