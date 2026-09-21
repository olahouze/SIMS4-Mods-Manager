from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.database import DatabaseManager, CatalogMod


@pytest.fixture
def client():
    DatabaseManager.get_instance()
    with TestClient(app) as c:
        yield c


def test_api_check_missing_report_already_reported(client):
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        mod = CatalogMod(
            source="loverslab",
            remote_id="rep_test_01",
            title="Report Test Mod",
            author="DevAuthor",
            category="Animations",
            page_url="https://loverslab.com/test-rep",
        )
        session.add(mod)
        session.commit()
        mod_id = mod.id

    mock_status = {
        "can_report": False,
        "already_reported": True,
        "reported_at": "12/09/2026 à 14:32",
        "formatted_message": "Hi @DevAuthor...",
        "author": "@DevAuthor",
        "is_authenticated": True,
        "reason": "Message déjà posté sur le forum le 12/09/2026 à 14:32.",
    }

    with patch(
        "src.application.dependencies.requirement_reporter_service.RequirementReporterService.check_report_status",
        return_value=mock_status,
    ):
        resp = client.post(
            "/api/catalog/check-missing-report",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": ["Missing Mod A", "Missing Mod B"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_reported"] is True
        assert data["can_report"] is False
        assert data["reported_at"] == "12/09/2026 à 14:32"
        assert data["author"] == "@DevAuthor"


def test_api_report_missing_requirements_submit(client):
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        mod = CatalogMod(
            source="loverslab",
            remote_id="rep_test_02",
            title="Report Test Mod 2",
            author="DevAuthor2",
            category="Animations",
            page_url="https://loverslab.com/test-rep-2",
        )
        session.add(mod)
        session.commit()
        mod_id = mod.id

    mock_submit_res = {
        "success": True,
        "message": "Message publié avec succès sur le forum LoversLab.",
        "already_reported": True,
        "reported_at": "à l'instant",
    }

    with patch(
        "src.application.dependencies.requirement_reporter_service.RequirementReporterService.submit_report",
        return_value=mock_submit_res,
    ):
        resp = client.post(
            "/api/catalog/report-missing-requirements",
            json={
                "catalog_mod_id": mod_id,
                "missing_modules": ["Missing Mod A"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["already_reported"] is True
        assert "succès" in data["message"]
