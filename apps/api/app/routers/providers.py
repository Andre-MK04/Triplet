from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.db.repositories.flights_repository import FlightsRepository
from app.providers.amadeus import AmadeusApiError, AmadeusAuthError, AmadeusConfigError
from app.providers.amadeus.client import AmadeusHttpClient, AmadeusNoResultsError
from app.providers.amadeus.mapper import map_amadeus_offers

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/status")
def provider_status() -> dict:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Provider diagnostics are disabled.")

    database_available = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_available = False

    warnings = []
    amadeus_configured = bool(settings.amadeus_client_id and settings.amadeus_client_secret)
    if not amadeus_configured:
        warnings.append("Amadeus credentials are missing.")

    return {
        "configuredProvider": settings.flight_provider,
        "databaseProviderAvailable": database_available,
        "amadeusConfigured": amadeus_configured,
        "amadeusBaseUrl": settings.amadeus_base_url,
        "cacheEnabled": settings.amadeus_cache_enabled,
        "warnings": warnings,
    }


@router.get("/smoke-test")
def provider_smoke_test() -> dict:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Provider diagnostics are disabled.")

    database = check_database()
    amadeus = {
        "configured": bool(settings.amadeus_client_id and settings.amadeus_client_secret),
        "authOk": False,
        "apiOk": False,
        "rawOffersCount": 0,
        "mappedFlightsCount": 0,
        "warnings": [],
    }
    warnings = []

    if settings.flight_provider == "database":
        overall = "ok" if database["available"] and database["cachedFlightsCount"] > 0 else "warning"
    elif settings.flight_provider == "hybrid" and not amadeus["configured"]:
        warnings.append("Hybrid provider is using database fallback because Amadeus credentials are missing.")
        overall = "ok" if database["available"] and database["cachedFlightsCount"] > 0 else "warning"
    elif settings.flight_provider in {"amadeus", "hybrid"}:
        amadeus = run_amadeus_smoke_test()
        overall = "ok" if amadeus["apiOk"] else "warning"
        if settings.flight_provider == "hybrid" and database["available"]:
            overall = "ok"
    else:
        warnings.append(f"Unknown provider '{settings.flight_provider}'.")
        overall = "warning"

    return {
        "configuredProvider": settings.flight_provider,
        "database": database,
        "amadeus": amadeus,
        "overallStatus": overall,
        "warnings": warnings,
    }


def check_database() -> dict:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            count = len(FlightsRepository(db).list_all_mock_flights())
            return {"available": True, "cachedFlightsCount": count}
    except SQLAlchemyError:
        return {"available": False, "cachedFlightsCount": 0}


def run_amadeus_smoke_test() -> dict:
    result = {
        "configured": bool(settings.amadeus_client_id and settings.amadeus_client_secret),
        "authOk": False,
        "apiOk": False,
        "rawOffersCount": 0,
        "mappedFlightsCount": 0,
        "warnings": [],
    }
    if not result["configured"]:
        result["warnings"].append("Amadeus credentials are missing.")
        return result

    try:
        payload = AmadeusHttpClient().get(
            "/v2/shopping/flight-offers",
            {
                "originLocationCode": "VIE",
                "destinationLocationCode": "ALC",
                "departureDate": "2026-07-12",
                "adults": 1,
                "currencyCode": "EUR",
                "max": 3,
                "nonStop": "true",
            },
        )
        result["authOk"] = True
        result["apiOk"] = True
        mapped = map_amadeus_offers(payload)
        result["rawOffersCount"] = mapped.raw_offers_count
        result["mappedFlightsCount"] = mapped.mapped_flights_count
        result["warnings"].extend(mapped.warnings)
    except AmadeusNoResultsError:
        result["authOk"] = True
        result["apiOk"] = True
        result["warnings"].append("Amadeus returned no offers for the smoke-test route.")
    except AmadeusConfigError as exc:
        result["warnings"].append(str(exc))
    except AmadeusAuthError as exc:
        result["warnings"].append(str(exc))
    except AmadeusApiError as exc:
        result["authOk"] = True
        result["warnings"].append(str(exc))

    return result
