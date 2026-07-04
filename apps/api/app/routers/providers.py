from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.db.repositories.flights_repository import FlightsRepository
from app.providers.registry import (
    LIVE_PROVIDER_NAMES,
    PROVIDER_NAMES,
    UnknownFlightProviderError,
    build_provider,
)
from app.rate_limit import rate_limit

router = APIRouter(prefix="/providers", tags=["providers"])


def require_dev_tools() -> None:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Provider diagnostics are disabled.")


@router.get("/status")
def provider_status() -> dict:
    require_dev_tools()

    database = check_database()
    statuses = []
    warnings: list[str] = []
    with SessionLocal() as db:
        for name in PROVIDER_NAMES:
            status = build_provider(name, db).get_provider_status()
            statuses.append(status.model_dump())
            warnings.extend(f"{name}: {warning}" for warning in status.warnings)

    return {
        "configuredProvider": settings.flight_provider,
        "liveProvider": settings.live_flight_provider,
        "database": database,
        "providers": statuses,
        "warnings": warnings,
    }


def provider_diagnostics_rate_limit(request: Request) -> None:
    rate_limit(
        "provider_smoke_test",
        settings.provider_smoke_test_rate_limit_max_attempts,
        settings.api_rate_limit_window_seconds,
    )(request)


@router.get("/smoke-test")
def provider_smoke_test(
    _: None = Depends(provider_diagnostics_rate_limit),
    provider: str | None = Query(None, min_length=3, max_length=20),
    origin: str = Query("VIE", min_length=3, max_length=3),
    destination: str = Query("ALC", min_length=3, max_length=3),
    departureDate: date | None = Query(None),
    maxResults: int = Query(3, ge=1, le=10),
) -> dict:
    require_dev_tools()

    provider_name = (provider or settings.live_flight_provider).lower()
    if provider_name not in PROVIDER_NAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider '{provider_name}'. Valid providers: {', '.join(PROVIDER_NAMES)}.",
        )

    database = check_database()
    with SessionLocal() as db:
        try:
            result = build_provider(provider_name, db).smoke_test(
                origin=origin.upper(),
                destination=destination.upper(),
                departure_date=departureDate,
                max_results=maxResults,
            )
        except UnknownFlightProviderError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    overall = "ok" if database["available"] and result.ok else "warning"
    if provider_name in LIVE_PROVIDER_NAMES and not result.ok and database["available"]:
        overall = "warning"

    return {
        "configuredProvider": settings.flight_provider,
        "liveProvider": settings.live_flight_provider,
        "query": {
            "provider": provider_name,
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departureDate": result.departureDate,
            "maxResults": maxResults,
        },
        "database": database,
        "result": result.model_dump(),
        "overallStatus": overall,
        "warnings": result.warnings,
    }


def check_database() -> dict:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            count = len(FlightsRepository(db).list_all_mock_flights())
            return {"available": True, "cachedFlightsCount": count}
    except SQLAlchemyError:
        return {"available": False, "cachedFlightsCount": 0}
