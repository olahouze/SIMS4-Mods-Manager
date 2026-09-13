# Contraintes Système de Fichiers & Moteur Les Sims 4

## 1. Règle Cruciale : Profondeur des Fichiers `.ts4script`
- Les fichiers Python compilés du jeu (`.ts4script`) **ne doivent jamais dépasser 1 seul niveau de sous-dossier** dans `Documents/Electronic Arts/Les Sims 4/Mods`.
- Exemple valide : `Mods/loverslab_WickedWhims_1042/WickedWhims.ts4script`
- Exemple invalide (non chargé par le moteur de jeu C++) : `Mods/loverslab_WickedWhims_1042/scripts/sub/WickedWhims.ts4script`
- Les fichiers `.package` supportent jusqu'à 5 niveaux d'arborescence, mais pour garantir la cohérence et la désinstallation propre, chaque mod est installé dans son dossier racine dédié.

---

## 2. Nommage et Assainissement des Dossiers de Mods
- Format obligatoire de nom de dossier : `{source}_{NomAssaini}_{xxx}` (ex: `loverslab_WickedWhims_1042`).
- Règle stricte d'assainissement : caractères alphanumériques et underscores uniquement (`[a-zA-Z0-9_]`).
- Supprimer systématiquement espaces, apostrophes, accents, diacritiques, emojis et signes de ponctuation.
- Le suffixe numérique aléatoire `_xxx` élimine les collisions lors de réinstallations ou de versions concurrentes.
