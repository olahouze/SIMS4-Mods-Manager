"""CatalogQueries: Re-exports build_catalog_query from infrastructure layer for backwards compatibility."""

from src.infrastructure.database.catalog_queries import build_catalog_query

__all__ = ["build_catalog_query"]
