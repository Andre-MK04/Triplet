from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def database_health() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return {"status": "unavailable"}

    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict:
    checks = {
        "database": {"ok": False},
        "provider": {
            "ok": True,
            "configuredProvider": settings.flight_provider,
            "providerName": "skyscanner" if settings.flight_provider in {"skyscanner", "hybrid"} else settings.flight_provider,
            "skyscannerApiEnabled": settings.skyscanner_api_enabled,
            "skyscannerApiKeyConfigured": bool(settings.skyscanner_api_key),
            "skyscannerAffiliateConfigured": bool(
                settings.skyscanner_affiliate_enabled and settings.skyscanner_media_partner_id
            ),
        },
        "ai": {"ok": not settings.ai_enabled or bool(settings.openai_api_key), "enabled": settings.ai_enabled},
    }

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"]["ok"] = True
    except SQLAlchemyError:
        checks["database"]["error"] = "unavailable"

    if settings.flight_provider == "skyscanner" and not (
        settings.skyscanner_api_enabled and settings.skyscanner_api_key
    ):
        checks["provider"]["ok"] = False
        checks["provider"]["error"] = "Skyscanner API access is not configured."

    status = "ready" if all(check["ok"] for check in checks.values()) else "degraded"
    return {"status": status, "environment": settings.app_env, "checks": checks}
