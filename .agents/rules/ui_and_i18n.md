# Interface Utilisateur PySide6 & Internationalisation (i18n)

## 1. Architecture Multi-Vues & Signaux Croisés
- Toute mutation d'état (installation, désinstallation, mise à jour, changement d'état d'un mod) émet un signal connecté au coordinateur central `App._on_mods_state_changed()`.
- Ce coordinateur garantit la cohérence en temps réel de toutes les vues actives :
  - `InstalledView` (grille de tuiles `InstalledCard`)
  - `UpdatesView` (détection des nouvelles versions disponibles)
  - `CatalogView` (bascule des boutons d'action sur `✓ Déjà Installé`)
  - Badges de notification de la barre de navigation
  - `ModDetailView` si ouverte

---

## 2. Ségrégation des Threads UI & Workers Asynchrones
- L'interface ne doit **jamais** exécuter d'appels réseau, d'extraction d'archives ou de requêtes lourdes sur le thread principal PySide6.
- Utiliser systématiquement les workers `QThread` dédiés de `src/ui/workers/` (`CatalogFetchWorker`, `CatalogStatsWorker`, `ModDetailFetchWorker`, `GalleryBatchWorker`, etc.).

---

## 3. Internationalisation Dynamique (i18n)
- **Singleton `I18nManager` (`src/i18n.py`)** : Charge les catalogues JSON depuis `src/locales/{fr,en,es}.json` et émet le signal `language_changed(lang: str)`.
- **Fonction canonique `tr(key, **kwargs)`** : Accès aux clés avec interpolation de variables et repli automatique sur le français si la clé est absente.
- **Règle de Parité Stricte 100%** : Toute nouvelle clé ajoutée dans un fichier de locale doit **obligatoirement** être répliquée avec exactitude dans `fr.json`, `en.json` et `es.json`.
- **Retraduction à Chaud (`retranslate_ui`)** : Chaque vue ou composant implémente la méthode `retranslate_ui()` connectée au signal `language_changed` pour basculer instantanément les libellés, placeholders et tooltips sans redémarrage de l'application.

---

## 4. Composants Réutilisables & Optimisations Graphiques
- **Grille Dynamique `ResponsiveCardGrid`** : Calcule le nombre de colonnes en fonction de la largeur disponible et réordonne les cartes existantes sans réinstanciation pour éliminer les scintillements visuels.
- **`DependenciesSummaryWidget`** : Standardise l'affichage synthétique des prérequis et des DLCs Sims 4 entre cartes et détails.
- **Factorisation des Dialogues `DialogHelper`** : Centralise les boîtes de dialogue modales (confirmation, information, alerte) avec le thème sombre premium.
- **Cache d'Images LRU `ImageCache`** : Cache mémoire thread-safe à budget d'octets fixe (128 Mo) prévenant les fuites mémoires et le redimensionnement redondant.
- **Polling Adaptatif (`CatalogView`)** : Fréquence de polling adaptative (4000 ms en veille, 600 ms lors d'un scraping actif).
