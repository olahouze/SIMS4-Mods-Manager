"""
FastAPI sub-router for reporting missing mod requirements and saving qualification overrides.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas.catalog import (
    CheckMissingReportRequest,
    CheckMissingReportResponse,
    SubmitMissingReportRequest,
    SubmitMissingReportResponse,
    RequirementsOverrideRequest,
)
from src.database.models import CatalogMod
from src.application.dependencies.requirement_reporter_service import RequirementReporterService
from src.utils.logger import logger

reports_router = APIRouter(tags=["Catalog Reports"])


@reports_router.post("/check-missing-report", response_model=CheckMissingReportResponse)
def check_missing_report(payload: CheckMissingReportRequest, session: Session = Depends(get_db)):
    """Checks live on the provider forum if user has already commented about missing requirements."""
    cat_mod = None
    if payload.catalog_mod_id:
        cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
    elif payload.source and payload.remote_id:
        cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

    page_url = str((cat_mod.page_url if cat_mod else payload.page_url) or "")
    source = str((cat_mod.source if cat_mod else payload.source) or "loverslab")
    mod_title = str((cat_mod.title if cat_mod else payload.title) or "Mod")
    author = str((cat_mod.author if cat_mod else payload.author) or "Author")

    status = RequirementReporterService.check_report_status(
        source=source,
        page_url=page_url,
        mod_title=mod_title,
        author=author,
        missing_modules=payload.missing_modules,
        unnecessary_modules=payload.unnecessary_modules,
    )
    return CheckMissingReportResponse(**status)


@reports_router.post("/report-missing-requirements", response_model=SubmitMissingReportResponse)
def report_missing_requirements(payload: SubmitMissingReportRequest, session: Session = Depends(get_db)):
    """Posts a standardized message on the provider forum to notify the author about missing requirements."""
    cat_mod = None
    if payload.catalog_mod_id:
        cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
    elif payload.source and payload.remote_id:
        cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

    page_url = str((cat_mod.page_url if cat_mod else payload.page_url) or "")
    source = str((cat_mod.source if cat_mod else payload.source) or "loverslab")
    mod_title = str((cat_mod.title if cat_mod else payload.title) or "Mod")
    author = str((cat_mod.author if cat_mod else payload.author) or "Author")

    res = RequirementReporterService.submit_report(
        source=source,
        page_url=page_url,
        mod_title=mod_title,
        author=author,
        missing_modules=payload.missing_modules,
        unnecessary_modules=payload.unnecessary_modules,
        custom_message=payload.custom_message,
    )
    return SubmitMissingReportResponse(**res)


@reports_router.post("/requirements-override")
def save_requirements_override(payload: RequirementsOverrideRequest, session: Session = Depends(get_db)):
    """Saves user qualification ('MOD' vs 'COMMENT') for mod requirements."""
    cat_mod = None
    if payload.catalog_mod_id:
        cat_mod = session.query(CatalogMod).filter_by(id=payload.catalog_mod_id).first()
    elif payload.source and payload.remote_id:
        cat_mod = session.query(CatalogMod).filter_by(source=payload.source, remote_id=payload.remote_id).first()

    if not cat_mod:
        raise HTTPException(status_code=404, detail="Mod introuvable dans le catalogue.")

    current = cat_mod.get_requirements_overrides()
    current.update(payload.overrides)
    cat_mod.set_requirements_overrides(current)
    session.commit()
    logger.info(f"Overrides de prérequis mis à jour pour '{cat_mod.title}': {payload.overrides}")
    return {"success": True, "overrides": current}
