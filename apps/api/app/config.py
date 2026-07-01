import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    app_name: str = os.getenv("APP_NAME", "Triplet")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://triplet:triplet@localhost:5433/triplet",
    )
    flight_provider: str = os.getenv("FLIGHT_PROVIDER", "database")
    enable_dev_tool_endpoints: bool = os.getenv("ENABLE_DEV_TOOL_ENDPOINTS", "true").lower() == "true"
    amadeus_client_id: str | None = os.getenv("AMADEUS_CLIENT_ID") or None
    amadeus_client_secret: str | None = os.getenv("AMADEUS_CLIENT_SECRET") or None
    amadeus_base_url: str = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
    amadeus_timeout_seconds: float = float(os.getenv("AMADEUS_TIMEOUT_SECONDS", "20"))
    amadeus_max_requests_per_search: int = int(os.getenv("AMADEUS_MAX_REQUESTS_PER_SEARCH", "40"))
    amadeus_cache_enabled: bool = os.getenv("AMADEUS_CACHE_ENABLED", "true").lower() == "true"
    ai_enabled: bool = os.getenv("AI_ENABLED", "false").lower() == "true"
    ai_provider: str = os.getenv("AI_PROVIDER", "openai")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    openai_reasoning_effort: str = os.getenv("OPENAI_REASONING_EFFORT", "low")
    ai_max_tool_calls: int = int(os.getenv("AI_MAX_TOOL_CALLS", "3"))
    ai_require_tool_results: bool = os.getenv("AI_REQUIRE_TOOL_RESULTS", "true").lower() == "true"
    ai_max_trips_sent_to_model: int = int(os.getenv("AI_MAX_TRIPS_SENT_TO_MODEL", "8"))
    ai_max_input_tokens_hint: int = int(os.getenv("AI_MAX_INPUT_TOKENS_HINT", "12000"))
    ai_daily_request_limit_placeholder: int = int(os.getenv("AI_DAILY_REQUEST_LIMIT_PLACEHOLDER", "100"))
    app_secret: str = os.getenv("APP_SECRET", "dev-secret-change-me")
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    auth_access_token_expire_minutes: int = int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    auth_refresh_token_expire_days: int = int(os.getenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    auth_cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
    auth_cookie_domain: str | None = os.getenv("AUTH_COOKIE_DOMAIN") or None
    auth_password_min_length: int = int(os.getenv("AUTH_PASSWORD_MIN_LENGTH", "12"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    auth_rate_limit_window_seconds: int = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))
    auth_rate_limit_max_attempts: int = int(os.getenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", "20"))
    auth_public_base_url: str = os.getenv("AUTH_PUBLIC_BASE_URL", "http://localhost:8001")
    google_oauth_client_id: str | None = os.getenv("GOOGLE_OAUTH_CLIENT_ID") or None
    google_oauth_client_secret: str | None = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or None
    apple_oauth_client_id: str | None = os.getenv("APPLE_OAUTH_CLIENT_ID") or None
    apple_oauth_client_secret: str | None = os.getenv("APPLE_OAUTH_CLIENT_SECRET") or None
    apple_oauth_team_id: str | None = os.getenv("APPLE_OAUTH_TEAM_ID") or None
    apple_oauth_key_id: str | None = os.getenv("APPLE_OAUTH_KEY_ID") or None
    apple_oauth_private_key: str | None = os.getenv("APPLE_OAUTH_PRIVATE_KEY") or None
    billing_enabled: bool = os.getenv("BILLING_ENABLED", "false").lower() == "true"
    billing_provider: str = os.getenv("BILLING_PROVIDER", "stripe")
    stripe_secret_key: str | None = os.getenv("STRIPE_SECRET_KEY") or None
    stripe_publishable_key: str | None = os.getenv("STRIPE_PUBLISHABLE_KEY") or None
    stripe_webhook_secret: str | None = os.getenv("STRIPE_WEBHOOK_SECRET") or None
    stripe_price_pro_monthly: str | None = os.getenv("STRIPE_PRICE_PRO_MONTHLY") or None
    stripe_price_pro_yearly: str | None = os.getenv("STRIPE_PRICE_PRO_YEARLY") or None
    billing_success_url: str = os.getenv("BILLING_SUCCESS_URL", "http://localhost:3000/billing/success")
    billing_cancel_url: str = os.getenv("BILLING_CANCEL_URL", "http://localhost:3000/pricing")
    billing_portal_return_url: str = os.getenv("BILLING_PORTAL_RETURN_URL", "http://localhost:3000/dashboard")
    triplet_free_saved_search_limit: int = int(os.getenv("TRIPLET_FREE_SAVED_SEARCH_LIMIT", "3"))
    triplet_free_ai_searches_per_day: int = int(os.getenv("TRIPLET_FREE_AI_SEARCHES_PER_DAY", "5"))
    triplet_free_max_origin_airports: int = int(os.getenv("TRIPLET_FREE_MAX_ORIGIN_AIRPORTS", "6"))
    triplet_free_alert_frequencies: str = os.getenv("TRIPLET_FREE_ALERT_FREQUENCIES", "daily")
    triplet_pro_saved_search_limit: int = int(os.getenv("TRIPLET_PRO_SAVED_SEARCH_LIMIT", "30"))
    triplet_pro_ai_searches_per_day: int = int(os.getenv("TRIPLET_PRO_AI_SEARCHES_PER_DAY", "100"))
    triplet_pro_max_origin_airports: int = int(os.getenv("TRIPLET_PRO_MAX_ORIGIN_AIRPORTS", "12"))
    triplet_pro_alert_frequencies: str = os.getenv("TRIPLET_PRO_ALERT_FREQUENCIES", "daily,weekly")
    alerts_enabled: bool = os.getenv("ALERTS_ENABLED", "false").lower() == "true"
    alerts_default_frequency: str = os.getenv("ALERTS_DEFAULT_FREQUENCY", "daily")
    alerts_max_results_per_email: int = int(os.getenv("ALERTS_MAX_RESULTS_PER_EMAIL", "5"))
    alerts_min_hours_between_notifications: int = int(os.getenv("ALERTS_MIN_HOURS_BETWEEN_NOTIFICATIONS", "24"))
    alerts_public_base_url: str = os.getenv("ALERTS_PUBLIC_BASE_URL", "http://localhost:3000")
    email_provider: str = os.getenv("EMAIL_PROVIDER", "console")
    email_from: str = os.getenv("EMAIL_FROM", "alerts@triplet.local")
    smtp_host: str | None = os.getenv("SMTP_HOST") or None
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME") or None
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or None
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"


settings = Settings()
