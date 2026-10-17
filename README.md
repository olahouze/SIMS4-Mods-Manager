# ⚠️ Dépôt Déprécié & Migré / Deprecated & Migrated Repository

> [!WARNING]
> **Ce dépôt n'est plus maintenu ici.**
> Le projet a officiellement déménagé vers un nouveau dépôt actif bénéficiant d'une refonte architecturale complète (POO 3-tiers), d'optimisations majeures et d'une suite de tests modernisée.
> 
> 👉 **Nouveau dépôt officiel : [https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager)**

---

## 🇫🇷 Informations sur la Migration

Le développement actif du **Sims 4 Mods Manager** se poursuit désormais sous l'organisation / compte **pleasurecreator610-boop**.

### Pourquoi cette migration ?
- **Nouvelle architecture 3-tiers POO** : Découplage strict entre Orchestration (`*_orchestrator`), Coordination de flux/boucles (`*_coordinator`) et Actions atomiques (`*_actions`).
- **Performance & Stabilité** : Amélioration du traitement des archives, des dépendances et du cache.
- **Suite de tests unifiée** : Séparation rigoureuse entre tests unitaires (`tests/unit/`) et tests de bout en bout (`tests/e2e/`).
- **Documentation technique exhaustive & Roadmap** : Refonte complète de la documentation et guide d'optimisation.

### Mettre à jour votre clone local

Si vous aviez cloné ce dépôt, vous pouvez simplement mettre à jour l'URL de votre remote `origin` :

```bash
git remote set-url origin https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager.git
git fetch origin
git checkout dev # ou main
```

---

## 🇬🇧 Migration Notice

> [!NOTE]
> This repository is archived and no longer actively maintained.
> All development has moved to:
> **[https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager)**

Please update your git remotes and bookmarks to the new address.
