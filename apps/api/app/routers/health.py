from fastapi import APIRouter, Response
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
    """Whether the service can serve traffic.

    Production answers with a verdict and nothing else. The detailed view names
    the configured flight provider, whether AI is on and how the provider
    authenticated — a useful map for anyone deciding what to attack, and of no
    use to a load balancer, which only needs to know whether to route here.
    """
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
    if settings.app_env in {"production", "prod"} and not settings.expose_api_docs:
        # A load balancer needs the verdict; nobody outside needs the map.
        return {"status": status}
    return {"status": status, "environment": settings.app_env, "checks": checks}


@router.get("/auth/csrf")
def csrf_token(response: Response) -> dict[str, str]:
    """Hand the frontend a CSRF token.

    In production the frontend is proxied same-origin, so it simply reads the
    cookie. Local development talks to the API cross-origin, where the cookie is
    not readable from the page — so the token is also returned in the body,
    which a credentialed fetch can read. Both paths get the same token, and it
    is not a credential on its own.
    """
    from app.security import csrf

    token = csrf.issue_token()
    csrf.set_cookie(response, token)
    return {"token": token}
