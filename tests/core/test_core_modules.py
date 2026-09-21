from datetime import datetime

from src.core.constants import ProviderType, RequirementStatus, PatreonStatus
from src.core.exceptions import (
    Sims4ManagerError,
    ApiClientError,
    ApiConnectionError,
    ProviderError,
    ProviderScrapeError,
    ModDownloadError,
    ModArchiveError,
    DependencyResolutionError,
)
from src.core.dto import ModDetailsDTO, DownloadResultDTO


def test_core_constants():
    assert ProviderType.LOVERSLAB == "loverslab"
    assert ProviderType.PATREON == "patreon"
    assert ProviderType.MANUAL == "manual"

    assert RequirementStatus.NONE == "NONE"
    assert RequirementStatus.RESOLVED == "RESOLVED"
    assert RequirementStatus.PENDING_VERIFICATION == "PENDING_VERIFICATION"

    assert PatreonStatus.PUBLIC == "PUBLIC"
    assert PatreonStatus.LOCKED == "LOCKED"
    assert PatreonStatus.UNLOCKED == "UNLOCKED"


def test_core_exceptions():
    err = ApiClientError("Forbidden", status_code=403)
    assert str(err) == "Forbidden"
    assert err.status_code == 403
    assert isinstance(err, Sims4ManagerError)

    conn_err = ApiConnectionError("Connection refused")
    assert isinstance(conn_err, ApiClientError)

    prov_err = ProviderScrapeError("Scraping failed")
    assert isinstance(prov_err, ProviderError)

    dl_err = ModDownloadError("Download error")
    assert isinstance(dl_err, ProviderError)

    arch_err = ModArchiveError("Archive broken")
    assert isinstance(arch_err, Sims4ManagerError)

    dep_err = DependencyResolutionError("Missing dependency")
    assert isinstance(dep_err, Sims4ManagerError)


def test_core_dtos():
    dto = ModDetailsDTO(
        remote_id="123",
        title="Test Mod",
        page_url="https://example.com",
        author="AuthorX",
        published_date=datetime(2026, 1, 1, 12, 0),
    )
    d = dto.to_dict()
    assert d["remote_id"] == "123"
    assert d["title"] == "Test Mod"
    assert "published_date" in d

    dto2 = ModDetailsDTO.from_dict(
        {"remote_id": "456", "title": "Second Mod", "page_url": "https://example.com/2", "extra_ignored": "foo"}
    )
    assert dto2.remote_id == "456"

    res = DownloadResultDTO(
        success=True,
        file_path="downloads/mod.zip",
        file_size_bytes=1024,
        message="OK",
    )
    assert res.success is True
    assert res.file_size_bytes == 1024
