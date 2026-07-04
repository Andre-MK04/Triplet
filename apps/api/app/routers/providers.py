from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.db.repositories.flights_repository import FlightsRepository
from app.providers.skyscanner.affiliate_links import SkyscannerAffiliateLinkBuilder
from app.providers.skyscanner.client import (
    SkyscannerApiError,
    SkyscannerAuthError,
    SkyscannerConfigError,
    SkyscannerHttpClient,
    SkyscannerNoResultsError,
)
from app.providers.skyscanner.flight_provider import build_one_way_live_search_payload
from app.providers.skyscanner.mapper import map_live_response_to_flights
from app.rate_limit import rate_limit

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/status")
def provider_status() -> dict:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Provider diagnostics are disabled.")

    database = check_database()
    warnings = []
    if settings.flight_provider in {"skyscanner", "hybrid"} and not settings.skyscanner_api_key:
        warnings.append("Skyscanner API key is missing.")
    if settings.skyscanner_affiliate_enabled and not settings.skyscanner_media_partner_id:
        warnings.append("Skyscanner affiliate media partner ID is missing.")

    return {
        "configuredProvider": settings.flight_provider,
        "database": database,
        "skyscanner": skyscanner_config_status(),
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
    origin: str = Query("VIE", min_length=3, max_length=3),
    destination: str = Query("ALC", min_length=3, max_length=3),
    departureDate: date = Query(date(2026, 8, 15)),
    maxResults: int = Query(3, ge=1, le=10),
) -> dict:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Provider diagnostics are disabled.")

    database = check_database()
    query = {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "departureDate": departureDate.isoformat(),
        "maxResults": maxResults,
    }
    skyscanner = run_skyscanner_smoke_test(query["origin"], query["destination"], departureDate, maxResults)
    overall = "ok" if database["available"] and (skyscanner["apiOk"] or skyscanner["affiliateLinkGenerated"]) else "warning"
    if settings.flight_provider == "database" and database["available"]:
        overall = "ok"

    return {
        "configuredProvider": settings.flight_provider,
        "query": query,
        "database": database,
        "skyscanner": skyscanner,
        "overallStatus": overall,
        "warnings": skyscanner["warnings"],
    }


def check_database() -> dict:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            count = len(FlightsRepository(db).list_all_mock_flights())
            return {"available": True, "cachedFlightsCount": count}
    except SQLAlchemyError:
        return {"available": False, "cachedFlightsCount": 0}


def skyscanner_config_status() -> dict:
    return {
        "configured": bool(settings.skyscanner_api_key or settings.skyscanner_media_partner_id),
        "apiEnabled": settings.skyscanner_api_enabled,
        "apiKeyConfigured": bool(settings.skyscanner_api_key),
        "affiliateEnabled": settings.skyscanner_affiliate_enabled,
        "mediaPartnerIdConfigured": bool(settings.skyscanner_media_partner_id),
        "baseUrl": settings.skyscanner_base_url,
        "market": settings.skyscanner_market,
        "locale": settings.skyscanner_locale,
        "currency": settings.skyscanner_currency,
        "cacheEnabled": settings.skyscanner_cache_enabled,
    }


def run_skyscanner_smoke_test(origin: str, destination: str, departure_date: date, max_results: int = 3) -> dict:
    result = {
        **skyscanner_config_status(),
        "apiOk": False,
        "createOk": False,
        "pollOk": False,
        "origin": origin.upper(),
        "destination": destination.upper(),
        "departureDate": departure_date.isoformat(),
        "rawOffersCount": 0,
        "mappedFlightsCount": 0,
        "skippedOffersCount": 0,
        "deepLinksReturned": 0,
        "affiliateLinkGenerated": False,
        "firstMappedFlight": None,
        "warnings": [],
    }

    builder = SkyscannerAffiliateLinkBuilder()
    affiliate_link = builder.build_day_view_link(origin, destination, departure_date, utm_term=f"{origin}-{destination}")
    if affiliate_link:
        result["affiliateLinkGenerated"] = True
        result["affiliateUrl"] = affiliate_link

    if not settings.skyscanner_api_enabled:
        result["warnings"].append("Skyscanner API is disabled.")
        if not result["affiliateLinkGenerated"]:
            result["warnings"].append("Skyscanner affiliate link is not configured.")
        return result
    if not settings.skyscanner_api_key:
        result["warnings"].append("Skyscanner API key is missing.")
        return result

    try:
        payload = build_one_way_live_search_payload(origin, destination, departure_date)
        client = SkyscannerHttpClient()
        response = client.run_live_price_search(payload)
        result["createOk"] = True
        result["pollOk"] = True
        result["apiOk"] = True
        mapped = map_live_response_to_flights(response)
        result["rawOffersCount"] = mapped.raw_offers_count
        result["mappedFlightsCount"] = mapped.mapped_flights_count
        result["skippedOffersCount"] = mapped.skipped_offers_count
        result["deepLinksReturned"] = mapped.deep_links_returned
        result["warnings"].extend(mapped.warnings)
        if mapped.flights:
            first = mapped.flights[0]
            result["firstMappedFlight"] = {
                "origin": first.origin,
                "destination": first.destination,
                "departureDateTime": first.departureDateTime.isoformat(),
                "price": first.price,
                "currency": first.currency,
                "deepLinkPresent": bool(first.deepLink),
            }
    except SkyscannerNoResultsError:
        result["createOk"] = True
        result["pollOk"] = True
        result["apiOk"] = True
        result["warnings"].append("Skyscanner returned no flight offers for the smoke-test route.")
    except (SkyscannerConfigError, SkyscannerAuthError, SkyscannerApiError) as exc:
        result["warnings"].append(str(exc))

    return result
