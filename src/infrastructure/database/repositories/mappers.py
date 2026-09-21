"""Mappeurs entre les modèles ORM SQLAlchemy et les entités du domaine pur."""

from __future__ import annotations

from src.database.models import AccountSession, CatalogMod, InstalledMod
from src.domain.models.account_entity import AccountSessionEntity
from src.domain.models.mod_entity import CatalogModEntity, InstalledModEntity


class ModelMapper:
    """Transformations bidirectionnelles entre modèles SQLAlchemy et entités de domaine."""

    @staticmethod
    def catalog_to_entity(model: CatalogMod) -> CatalogModEntity:
        return CatalogModEntity(
            id=model.id,
            source=model.source,
            remote_id=model.remote_id,
            title=model.title,
            author=model.author or "",
            category=model.category or "",
            tags=model.get_tags_list(),
            description=model.description or "",
            page_url=model.page_url,
            thumbnail_url=model.thumbnail_url or "",
            download_urls=model.get_download_urls_list(),
            external_links=model.get_external_links_list(),
            published_date=model.published_date,
            updated_date=model.updated_date,
            version_str=model.version_str or "",
            patreon_status=model.patreon_status or "NONE",
            patreon_tier=model.patreon_tier or "",
            requirements_text=model.requirements_text,
            requirements_status=model.requirements_status or "NONE",
            requirements_mods_json=model.get_requirements_mods_list(),
            requirements_overrides_json=model.get_requirements_overrides(),
            last_scraped_at=model.last_scraped_at,
        )

    @staticmethod
    def catalog_to_model(entity: CatalogModEntity, model: CatalogMod | None = None) -> CatalogMod:
        target = model or CatalogMod()
        target.source = entity.source
        target.remote_id = entity.remote_id
        target.title = entity.title
        target.author = entity.author
        target.category = entity.category
        target.set_tags_list(entity.tags)
        target.description = entity.description
        target.page_url = entity.page_url
        target.thumbnail_url = entity.thumbnail_url
        target.set_download_urls_list(entity.download_urls)
        target.set_external_links_list(entity.external_links)
        target.published_date = entity.published_date
        target.updated_date = entity.updated_date
        target.version_str = entity.version_str
        target.patreon_status = entity.patreon_status
        target.patreon_tier = entity.patreon_tier
        target.requirements_text = entity.requirements_text
        target.requirements_status = entity.requirements_status
        target.set_requirements_mods_list(entity.requirements_mods_json)
        target.set_requirements_overrides(entity.requirements_overrides_json)
        if entity.last_scraped_at:
            target.last_scraped_at = entity.last_scraped_at
        return target

    @staticmethod
    def installed_to_entity(model: InstalledMod) -> InstalledModEntity:
        catalog_ent = ModelMapper.catalog_to_entity(model.catalog_mod) if model.catalog_mod else None
        return InstalledModEntity(
            id=model.id,
            catalog_mod_id=model.catalog_mod_id,
            source=model.source,
            remote_id=model.remote_id or "",
            title=model.title,
            folder_name=model.folder_name,
            installed_files=model.get_installed_files_list(),
            installed_date=model.installed_date,
            version_date=model.version_date,
            version_str=model.version_str or "",
            is_enabled=bool(model.is_enabled),
            backup_path=model.backup_path,
            catalog_mod=catalog_ent,
        )

    @staticmethod
    def installed_to_model(entity: InstalledModEntity, model: InstalledMod | None = None) -> InstalledMod:
        target = model or InstalledMod()
        target.catalog_mod_id = entity.catalog_mod_id
        target.source = entity.source
        target.remote_id = entity.remote_id
        target.title = entity.title
        target.folder_name = entity.folder_name
        target.set_installed_files_list(entity.installed_files)
        if entity.installed_date:
            target.installed_date = entity.installed_date
        target.version_date = entity.version_date
        target.version_str = entity.version_str
        target.is_enabled = entity.is_enabled
        target.backup_path = entity.backup_path
        return target

    @staticmethod
    def account_to_entity(model: AccountSession) -> AccountSessionEntity:
        return AccountSessionEntity(
            provider_name=model.provider_name,
            is_authenticated=bool(model.is_authenticated),
            user_display_name=model.user_display_name or "",
            cookies_data=model.get_cookies_dict(),
            user_agent=model.user_agent or "",
            last_verified=model.last_verified,
        )

    @staticmethod
    def account_to_model(entity: AccountSessionEntity, model: AccountSession | None = None) -> AccountSession:
        target = model or AccountSession()
        target.provider_name = entity.provider_name
        target.is_authenticated = entity.is_authenticated
        target.user_display_name = entity.user_display_name
        target.set_cookies_dict(entity.cookies_data)
        target.user_agent = entity.user_agent
        if entity.last_verified:
            target.last_verified = entity.last_verified
        return target
