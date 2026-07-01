from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.auth import routes as auth_routes
from app.config import settings
from app.billing import routes as billing_routes
from app.routers import ai, alerts, airports, health, me, providers, tools, trips

allowed_origins = ["http://localhost:3000", "http://localhost:3001"]
if settings.frontend_url not in allowed_origins:
    allowed_origins.append(settings.frontend_url)

unsafe_methods = {"POST", "PUT", "PATCH", "DELETE"}
insecure_dev_secret = "dev-secret-change-me"


def validate_security_settings() -> None:
    if settings.environment.lower() == "production":
        if settings.app_secret == insecure_dev_secret:
            raise RuntimeError("APP_SECRET must be changed in production.")
        if not settings.auth_cookie_secure:
            raise RuntimeError("AUTH_COOKIE_SECURE=true is required in production.")


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
    origin = request.headers.get("origin")
    is_oauth_callback = request.url.path.startswith("/auth/oauth/") and request.url.path.endswith("/callback")
    if request.method in unsafe_methods and origin and origin not in allowed_origins and not is_oauth_callback:
        return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if settings.auth_cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

app.include_router(health.router)
app.include_router(airports.router)
app.include_router(trips.router)
app.include_router(tools.router)
app.include_router(ai.router)
app.include_router(providers.router)
app.include_router(alerts.router)
app.include_router(auth_routes.router)
app.include_router(me.router)
app.include_router(billing_routes.router)
