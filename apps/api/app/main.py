from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.auth import routes as auth_routes
from app.config import settings
from app.billing import routes as billing_routes
from app.providers.registry import LIVE_PROVIDER_NAMES, build_provider
from app.routers import ai, alerts, airports, geo, health, me, providers, tools, trips

allowed_origins = ["http://localhost:3000", "http://localhost:3001"]
if settings.frontend_url not in allowed_origins:
    allowed_origins.append(settings.frontend_url)

unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}
insecure_dev_secret = "dev-secret-change-me"
logger = logging.getLogger(__name__)


def validate_security_settings() -> None:
    if settings.app_env.lower() != "production":
        return

    errors = []
    if settings.app_secret == insecure_dev_secret:
        errors.append("APP_SECRET must be changed in production.")
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
    if settings.ai_enabled and not settings.openai_api_key:
        errors.append("OPENAI_API_KEY is required when AI_ENABLED=true in production.")
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

    if settings.flight_provider == "hybrid":
        live_status = build_provider(settings.live_flight_provider).get_provider_status()
        if live_status.accessStatus != "available":
            logger.warning(
                "FLIGHT_PROVIDER=hybrid is running without %s API access; database fallback will be used.",
                settings.live_flight_provider,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_settings()
    yield


app = FastAPI(title="Triplet API", version="0.1.0", lifespan=lifespan)

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
    origin = request.headers.get("origin")
    is_oauth_callback = request.url.path.startswith("/auth/oauth/") and request.url.path.endswith("/callback")
    if request.method in unsafe_methods and origin and origin not in allowed_origins and not is_oauth_callback:
        return JSONResponse(
            {"detail": "Origin is not allowed."},
            status_code=403,
            headers={"X-Request-ID": request_id},
        )

    response = await call_next(request)
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
app.include_router(trips.router)
app.include_router(tools.router)
app.include_router(ai.router)
app.include_router(providers.router)
app.include_router(alerts.router)
app.include_router(auth_routes.router)
app.include_router(me.router)
app.include_router(billing_routes.router)
