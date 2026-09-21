# SIMS 4 Mods Manager - Documentation Technique

Bienvenue sur la documentation technique officielle du projet **SIMS 4 Mods Manager**.

Cette application de bureau industrielle permet l'exploration, l'installation, la mise à jour, la détection des dépendances et la gestion des mods pour Les Sims 4 (PC/Windows), en s'appuyant sur des fournisseurs comme LoversLab et Patreon.

---

## 🏛️ Architecture & Philosophie

L'application a été entièrement refondue selon les principes de la **Clean Architecture** et de la **Programmation Orientée Objet** avancée :

- **Couplage Faible & Haute Cohésion** : Séparation stricte entre Domaine, Infrastructure, Application, API REST et Interface Utilisateur (PySide6).
- **Isolation Front-Back** : L'interface utilisateur communique exclusivement par requêtes HTTP typées via l'API REST FastAPI. Aucune requête BDD directe depuis l'UI.
- **Étanchéité Back-Back** : Les échanges internes passent par des interfaces et contrats typés (Repositories, DTOs Pydantic v2).
- **Concurrence & Multithreading Optimisé** : Pool centralisé `ThreadPoolManager` (I/O et CPU), pools Qt `QThreadPool` et workers `GenericRunnable`, arrêt gracieux via `ShutdownManager`.
- **Qualité & Typage Strict** : 100% conforme Mypy, docstrings Google-Style vérifiés (> 90% couverture avec `interrogate`), formatage Ruff.

---

## 🧭 Plan de la Documentation

1. **Architecture** :
   - [Vue d'Ensemble](architecture.md)
   - [Architecture Détaillée & Hexagonale](architecture/ARCHITECTURE.md)
   - [APIs Internes & Contrats Back-to-Back](architecture/INTERNAL_APIS.md)
   - [Catalogue des Modules & Classes](modules_and_classes.md)
2. **Métier & Services** :
   - [Services Applicatifs & Providers](services_and_providers.md)
   - [Moteur de Résolution des Dépendances & Filtrage du Bruit](dependency_classification_and_noise.md)
3. **API REST** :
   - [Spécification & Routes REST API](api/REST_API.md)
   - [Guide de Référence Rapide API](api_reference.md)
4. **Référence Python** :
   - Documentation auto-générée des classes et fonctions via `mkdocstrings`.
