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
    from app.providers.registry import LIVE_PROVIDER_NAMES, build_provider

    live_name = (
        settings.live_flight_provider
        if settings.flight_provider == "hybrid"
        else settings.flight_provider
    )
    checks = {
        "database": {"ok": False},
        "provider": {
            "ok": True,
            "configuredProvider": settings.flight_provider,
            "providerName": live_name,
        },
        "ai": {"ok": not settings.ai_enabled or bool(settings.openai_api_key), "enabled": settings.ai_enabled},
    }

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"]["ok"] = True
    except SQLAlchemyError:
        checks["database"]["error"] = "unavailable"

    if settings.flight_provider in LIVE_PROVIDER_NAMES:
        provider_status = build_provider(settings.flight_provider).get_provider_status()
        checks["provider"]["accessStatus"] = provider_status.accessStatus
        if provider_status.accessStatus != "available":
            checks["provider"]["ok"] = False
            checks["provider"]["error"] = f"{settings.flight_provider} API access is not configured."

    status = "ready" if all(check["ok"] for check in checks.values()) else "degraded"
    return {"status": status, "environment": settings.app_env, "checks": checks}
