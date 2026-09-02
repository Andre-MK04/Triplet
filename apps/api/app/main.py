from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.auth import routes as auth_routes
from app.config import settings
from app.observability.context import set_request_id
from app.observability.logging import configure_logging
from app.observability.sentry import configure_sentry
from app.security import csrf
from app.security import (
    RateLimitExceeded,
    check_production_limits,
    limiter_backend_name,
    validate_for_production,
)
from app.billing import routes as billing_routes
from app.providers.registry import LIVE_PROVIDER_NAMES, build_provider
from app.routers import (
    ai,
    airports,
    alerts,
    countries,
    fare_feedback,
    featured,
    geo,
    health,
    me,
    places,
    providers,
    tools,
    travel_map,
    trips,
)

allowed_origins = ["http://localhost:3000", "http://localhost:3001"]
if settings.frontend_url not in allowed_origins:
    allowed_origins.append(settings.frontend_url)

unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}
insecure_dev_secret = "dev-secret-change-me"
logger = logging.getLogger(__name__)


#: RFC 7518 §3.2 — an HMAC-SHA256 key should be at least the hash length.
MIN_APP_SECRET_BYTES = 32


def validate_security_settings() -> None:
    if settings.app_env.lower() != "production":
        return

    errors = []
    if settings.app_secret == insecure_dev_secret:
        errors.append("APP_SECRET must be changed in production.")
    elif len(settings.app_secret.encode()) < MIN_APP_SECRET_BYTES:
        # This signs session tokens with HMAC-SHA256, and RFC 7518 §3.2 wants a
        # key at least as long as the hash output. A short secret is brute
        # forceable offline by anyone holding one token, which yields the
        # ability to mint sessions for any account.
        errors.append(
            f"APP_SECRET must be at least {MIN_APP_SECRET_BYTES} bytes "
            f"(currently {len(settings.app_secret.encode())}). "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    if not settings.database_url:
        errors.append("DATABASE_URL is required in production.")
    if not settings.frontend_url.startswith("https://"):
        errors.append("FRONTEND_URL must use HTTPS in production.")
    if not settings.api_public_base_url.startswith("https://"):
        errors.append("API_PUBLIC_BASE_URL must use HTTPS in production.")
    if not settings.auth_cookie_secure:
        errors.append("AUTH_COOKIE_SECURE=true is required in production.")
    if settings.auth_cookie_samesite.lower() == "none" and not settings.auth_cookie_secure:
        errors.append("AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true.")
    if "*" in allowed_origins:
        errors.append("Wildcard CORS origins are not allowed with credentials in production.")
    if settings.ai_enabled:
        # Validate the credential for the provider actually selected. This used
        # to demand OPENAI_API_KEY unconditionally, so an Anthropic deployment
        # could not start no matter how it was configured.
        provider = settings.ai_provider.strip().lower()
        required = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
        if provider not in required:
            errors.append(
                f"AI_PROVIDER={settings.ai_provider!r} is not a supported provider "
                f"({', '.join(sorted(required))})."
            )
        elif provider == "openai" and not settings.openai_api_key:
            errors.append("OPENAI_API_KEY is required when AI_ENABLED=true and AI_PROVIDER=openai.")
        elif provider == "anthropic" and not settings.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required when AI_ENABLED=true and AI_PROVIDER=anthropic.")
    if settings.flight_provider in LIVE_PROVIDER_NAMES:
        provider_status = build_provider(settings.flight_provider).get_provider_status()
        if provider_status.accessStatus != "available":
            errors.append(
                f"FLIGHT_PROVIDER={settings.flight_provider} requires the provider to be enabled and "
                f"configured ({', '.join(provider_status.requiredEnvVars)})."
            )
    if settings.billing_enabled:
        missing_billing = [
            name
            for name, value in {
                "STRIPE_SECRET_KEY": settings.stripe_secret_key,
                "STRIPE_WEBHOOK_SECRET": settings.stripe_webhook_secret,
                "STRIPE_PRICE_PRO_MONTHLY": settings.stripe_price_pro_monthly,
            }.items()
            if not value
        ]
        if missing_billing:
            errors.append(f"Billing is enabled but missing: {', '.join(missing_billing)}.")
    
    if settings.email_provider == "smtp" and not (
        settings.smtp_host and settings.smtp_username and settings.smtp_password
    ):
        errors.append("SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are required when EMAIL_PROVIDER=smtp.")

    if errors:
        raise RuntimeError("Production configuration is invalid: " + " ".join(errors))

    # Per-process limits are a real weakness beyond one worker, but not one worth
    # an outage over: warn on every boot, and fail only where the deployment has
    # declared it cannot tolerate them.
    warning = check_production_limits()
    if warning:
        logger.warning("rate_limit_configuration: %s", warning)
    fatal = validate_for_production()
    if fatal:
        raise RuntimeError("Production configuration is invalid: " + " ".join(fatal))
    logger.info("rate_limit_backend=%s", limiter_backend_name())

    if settings.flight_provider == "hybrid":
        live_status = build_provider(settings.live_flight_provider).get_provider_status()
        if live_status.accessStatus != "available":
            logger.warning(
                "FLIGHT_PROVIDER=hybrid is running without %s API access; database fallback will be used.",
                settings.live_flight_provider,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before validation, so anything it reports is already structured.
    configure_logging()
    configure_sentry()
    validate_security_settings()
    yield


# Docs are on by default outside production and off inside it, unless the
# operator turns them on deliberately with EXPOSE_API_DOCS.
_docs_enabled = settings.expose_api_docs or settings.app_env not in {"production", "prod"}

app = FastAPI(
    title="Triplet API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Answer an over-budget caller with something they can act on."""
    return JSONResponse(
        {"detail": "Too many requests. Please wait a moment and try again."},
        status_code=429,
        headers={
            "Retry-After": str(exc.retry_after_seconds),
            "Cache-Control": "no-store",
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_and_origin_check(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    # Every log line from here down carries it, including from code that knows
    # nothing about HTTP — otherwise a provider failure cannot be tied to the
    # search that caused it.
    set_request_id(request_id)
    origin = request.headers.get("origin")
    is_oauth_callback = request.url.path.startswith("/auth/oauth/") and request.url.path.endswith("/callback")
    if request.method in unsafe_methods and origin and origin not in allowed_origins and not is_oauth_callback:
        return JSONResponse(
            {"detail": "Origin is not allowed."},
            status_code=403,
            headers={"X-Request-ID": request_id},
        )

    # Origin checking above is kept as defence in depth, but it can only reject
    # an Origin it can see — a request arriving without the header passes it.
    # The CSRF token closes that, and covers only cookie-authenticated requests.
    csrf_error = csrf.check(request)
    if csrf_error:
        return JSONResponse(
            {"detail": csrf_error},
            status_code=403,
            headers={"X-Request-ID": request_id},
        )

    response = await call_next(request)

    # Make sure a browser session always has a usable token in hand.
    if csrf.CSRF_COOKIE_NAME not in request.cookies:
        csrf.set_cookie(response, csrf.issue_token())
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if settings.auth_cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

app.include_router(health.router)
app.include_router(airports.router)
app.include_router(geo.router)
app.include_router(places.router)
app.include_router(countries.router)
app.include_router(trips.router)
app.include_router(tools.router)
app.include_router(ai.router)
app.include_router(providers.router)
app.include_router(alerts.router)
app.include_router(featured.router)
app.include_router(fare_feedback.router)
app.include_router(auth_routes.router)
app.include_router(me.router)
app.include_router(travel_map.router)
app.include_router(billing_routes.router)
