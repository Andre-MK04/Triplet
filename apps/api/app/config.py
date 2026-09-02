import os

from dotenv import load_dotenv

load_dotenv()


def normalize_database_url(url: str) -> str:
    """Accept the postgres:// / postgresql:// URLs hosting providers hand out.

    We ship psycopg v3, so plain postgresql:// (which SQLAlchemy maps to
    psycopg2) must be rewritten to the explicit +psycopg driver scheme.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Settings:
    app_env: str = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "local"))
    environment: str = app_env
    app_name: str = os.getenv("APP_NAME", "Triplet")
    database_url: str = normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://triplet:triplet@localhost:5433/triplet",
        )
    )
    flight_provider: str = os.getenv("FLIGHT_PROVIDER", "database")
    live_flight_provider: str = os.getenv("LIVE_FLIGHT_PROVIDER", "travelpayouts")
    enable_dev_tool_endpoints: bool = os.getenv("ENABLE_DEV_TOOL_ENDPOINTS", "true").lower() == "true"
    duffel_api_enabled: bool = os.getenv("DUFFEL_API_ENABLED", "false").lower() == "true"
    duffel_api_key: str | None = os.getenv("DUFFEL_API_KEY") or None
    duffel_base_url: str = os.getenv("DUFFEL_BASE_URL", "https://api.duffel.com")
    duffel_api_version: str = os.getenv("DUFFEL_API_VERSION", "v2")
    duffel_timeout_seconds: float = float(os.getenv("DUFFEL_TIMEOUT_SECONDS", "30"))
    duffel_max_requests_per_search: int = int(os.getenv("DUFFEL_MAX_REQUESTS_PER_SEARCH", "10"))
    duffel_cache_enabled: bool = os.getenv("DUFFEL_CACHE_ENABLED", "true").lower() == "true"
    duffel_currency: str = os.getenv("DUFFEL_CURRENCY", "EUR")
    travelpayouts_api_enabled: bool = os.getenv("TRAVELPAYOUTS_API_ENABLED", "false").lower() == "true"
    travelpayouts_api_token: str | None = os.getenv("TRAVELPAYOUTS_API_TOKEN") or None
    travelpayouts_marker: str | None = os.getenv("TRAVELPAYOUTS_MARKER") or None
    travelpayouts_base_url: str = os.getenv("TRAVELPAYOUTS_BASE_URL", "https://api.travelpayouts.com")
    travelpayouts_affiliate_base_url: str = os.getenv("TRAVELPAYOUTS_AFFILIATE_BASE_URL", "https://www.aviasales.com")
    travelpayouts_timeout_seconds: float = float(os.getenv("TRAVELPAYOUTS_TIMEOUT_SECONDS", "20"))
    travelpayouts_max_requests_per_search: int = int(os.getenv("TRAVELPAYOUTS_MAX_REQUESTS_PER_SEARCH", "30"))
    travelpayouts_discovery_limit_per_origin: int = int(
        os.getenv("TRAVELPAYOUTS_DISCOVERY_LIMIT_PER_ORIGIN", "100")
    )
    travelpayouts_cache_enabled: bool = os.getenv("TRAVELPAYOUTS_CACHE_ENABLED", "true").lower() == "true"
    # How long a cached deal may be served before we re-read it from the
    # provider. The scheduled tick re-stamps rows hourly, so this only bites when
    # the tick is behind or the origin is one it does not warm.
    deals_serve_ttl_hours: int = int(os.getenv("DEALS_SERVE_TTL_HOURS", "6"))
    # How long a deal is kept at all. Longer than the serve window so a late tick
    # does not empty the cache and leave searches with nothing to fall back on.
    deals_retention_hours: int = int(os.getenv("DEALS_RETENTION_HOURS", "48"))
    # Refuse to quote a price the provider last saw longer ago than this. Their
    # data tops out around a week, so this is a backstop, not the main control —
    # fare age is primarily a ranking signal.
    max_fare_age_days: int = int(os.getenv("MAX_FARE_AGE_DAYS", "7"))
    # Multi-city totals are a SUM of legs, so each leg's staleness compounds — and
    # picking the cheapest fare per leg actively selects for stale ones, because a
    # price that has since risen still sits in the cache at its old value. Legs
    # prefer fares seen inside this window; a leg with nothing that fresh falls
    # back to what it has rather than dropping the route.
    itinerary_leg_fare_max_age_hours: int = int(os.getenv("ITINERARY_LEG_FARE_MAX_AGE_HOURS", "24"))
    # Origins the hourly tick keeps warm: one provider request each, so this is
    # the hourly API budget for cache warming.
    deals_max_warmed_origins: int = int(os.getenv("DEALS_MAX_WARMED_ORIGINS", "40"))
    travelpayouts_currency: str = os.getenv("TRAVELPAYOUTS_CURRENCY", "EUR")
    skyscanner_api_enabled: bool = os.getenv("SKYSCANNER_API_ENABLED", "false").lower() == "true"
    skyscanner_api_key: str | None = os.getenv("SKYSCANNER_API_KEY") or None
    skyscanner_base_url: str = os.getenv("SKYSCANNER_BASE_URL", "https://partners.api.skyscanner.net")
    skyscanner_timeout_seconds: float = float(os.getenv("SKYSCANNER_TIMEOUT_SECONDS", "20"))
    skyscanner_max_requests_per_search: int = int(os.getenv("SKYSCANNER_MAX_REQUESTS_PER_SEARCH", "30"))
    skyscanner_cache_enabled: bool = os.getenv("SKYSCANNER_CACHE_ENABLED", "true").lower() == "true"
    skyscanner_cache_max_age_hours: int = int(os.getenv("SKYSCANNER_CACHE_MAX_AGE_HOURS", "6"))
    skyscanner_market: str = os.getenv("SKYSCANNER_MARKET", "SI")
    skyscanner_locale: str = os.getenv("SKYSCANNER_LOCALE", "en-GB")
    skyscanner_currency: str = os.getenv("SKYSCANNER_CURRENCY", "EUR")
    skyscanner_use_indicative_prices: bool = os.getenv("SKYSCANNER_USE_INDICATIVE_PRICES", "true").lower() == "true"
    skyscanner_use_live_prices: bool = os.getenv("SKYSCANNER_USE_LIVE_PRICES", "true").lower() == "true"
    skyscanner_poll_attempts: int = int(os.getenv("SKYSCANNER_POLL_ATTEMPTS", "3"))
    skyscanner_poll_delay_seconds: float = float(os.getenv("SKYSCANNER_POLL_DELAY_SECONDS", "1"))
    skyscanner_affiliate_enabled: bool = os.getenv("SKYSCANNER_AFFILIATE_ENABLED", "true").lower() == "true"
    skyscanner_media_partner_id: str | None = os.getenv("SKYSCANNER_MEDIA_PARTNER_ID") or None
    skyscanner_affiliate_base_url: str = os.getenv(
        "SKYSCANNER_AFFILIATE_BASE_URL",
        "https://skyscanner.net/g/referrals/v1",
    )
    skyscanner_affiliate_utm_source: str = os.getenv("SKYSCANNER_AFFILIATE_UTM_SOURCE", "triplet")
    skyscanner_affiliate_utm_medium: str = os.getenv("SKYSCANNER_AFFILIATE_UTM_MEDIUM", "affiliate")
    skyscanner_affiliate_utm_campaign: str = os.getenv("SKYSCANNER_AFFILIATE_UTM_CAMPAIGN", "triplet_search")
    ai_enabled: bool = os.getenv("AI_ENABLED", "false").lower() == "true"
    ai_provider: str = os.getenv("AI_PROVIDER", "openai")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    anthropic_max_tokens: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1024"))
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
    api_public_base_url: str = os.getenv("API_PUBLIC_BASE_URL", os.getenv("AUTH_PUBLIC_BASE_URL", "http://localhost:8001"))
    auth_rate_limit_window_seconds: int = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300"))
    auth_rate_limit_max_attempts: int = int(os.getenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", "20"))
    auth_public_base_url: str = os.getenv("AUTH_PUBLIC_BASE_URL", api_public_base_url)
    api_rate_limit_window_seconds: int = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))
    trips_search_rate_limit_max_attempts: int = int(os.getenv("TRIPS_SEARCH_RATE_LIMIT_MAX_ATTEMPTS", "60"))
    ai_search_rate_limit_max_attempts: int = int(os.getenv("AI_SEARCH_RATE_LIMIT_MAX_ATTEMPTS", "20"))
    provider_smoke_test_rate_limit_max_attempts: int = int(os.getenv("PROVIDER_SMOKE_TEST_RATE_LIMIT_MAX_ATTEMPTS", "10"))
    rate_limit_cheap_per_window: int = int(os.getenv("RATE_LIMIT_CHEAP_PER_WINDOW", "240"))
    rate_limit_alerts_per_window: int = int(os.getenv("RATE_LIMIT_ALERTS_PER_WINDOW", "10"))
    # Counters are shared across processes when this is set. Without it each
    # worker enforces its own budget, which production must not rely on.
    redis_url: str | None = os.getenv("REDIS_URL") or None
    # Only trust X-Forwarded-For where a proxy actually sets it; otherwise a
    # caller could choose their own rate-limit identity.
    trust_proxy_headers: bool = os.getenv("TRUST_PROXY_HEADERS", "true").lower() == "true"
    # Refuse to start rather than run per-process limits. For multi-worker
    # deployments, where per-process counters really are ineffective. Off by
    # default: a missing variable must not crash-loop a running service.
    rate_limit_require_shared: bool = os.getenv("RATE_LIMIT_REQUIRE_SHARED", "false").lower() == "true"
    # Interactive API docs describe every route, schema and error to anyone who
    # asks. Useful locally, an inventory for an attacker in production.
    expose_api_docs: bool = os.getenv("EXPOSE_API_DOCS", "").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    # Optional error reporting. Absent by default: observability must not
    # require a paid vendor to work at all.
    sentry_dsn: str | None = os.getenv("SENTRY_DSN") or None
    # How long an anonymous watch's confirmation link stays valid, and how long
    # an unconfirmed watch is kept before cleanup removes it.
    watch_verification_ttl_hours: int = int(os.getenv("WATCH_VERIFICATION_TTL_HOURS", "48"))
    watch_unverified_retention_hours: int = int(os.getenv("WATCH_UNVERIFIED_RETENTION_HOURS", "168"))
    # A single address can only be pointed at so many unconfirmed watches before
    # it is being used as a mail target rather than a traveller's own inbox.
    watch_max_unverified_per_email: int = int(os.getenv("WATCH_MAX_UNVERIFIED_PER_EMAIL", "3"))
    # The homepage board. Assembled by the scheduled tick and served from the
    # database, so a page view never reaches a flight provider.
    featured_deal_origins: str | None = os.getenv("FEATURED_DEAL_ORIGINS") or None
    featured_deal_max_budget: float = float(os.getenv("FEATURED_DEAL_MAX_BUDGET", "250"))
    featured_deal_stale_after_hours: int = int(os.getenv("FEATURED_DEAL_STALE_AFTER_HOURS", "6"))
    # A ceiling on language-model calls per day across the whole service, so a
    # bug or an abuser cannot run up an unbounded bill. Reaching it degrades to
    # the rule-based parser rather than breaking search.
    ai_daily_request_limit: int = int(os.getenv("AI_DAILY_REQUEST_LIMIT", "2000"))
    ai_max_message_chars: int = int(os.getenv("AI_MAX_MESSAGE_CHARS", "2000"))
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
    # Anonymous/public visitors aren't on a plan; the public landing + discover
    # demo searches the Vienna region (6 airports), so cap them there rather than
    # at the logged-in Free limit.
    triplet_public_max_origin_airports: int = int(os.getenv("TRIPLET_PUBLIC_MAX_ORIGIN_AIRPORTS", "6"))
    # Accounts that run and test Triplet itself: every plan limit is lifted for
    # them. Comma-separated emails, configured per environment — never committed,
    # so this repository can stay public without naming anyone.
    triplet_owner_emails: str = os.getenv("TRIPLET_OWNER_EMAILS", "")
    # Free plan: for trying Triplet casually.
    triplet_free_saved_search_limit: int = int(os.getenv("TRIPLET_FREE_SAVED_SEARCH_LIMIT", "1"))
    triplet_free_ai_searches_per_month: int = int(os.getenv("TRIPLET_FREE_AI_SEARCHES_PER_MONTH", "3"))
    triplet_free_max_origin_airports: int = int(os.getenv("TRIPLET_FREE_MAX_ORIGIN_AIRPORTS", "3"))
    triplet_free_alert_frequencies: str = os.getenv("TRIPLET_FREE_ALERT_FREQUENCIES", "weekly")
    # Pro plan: for flexible travelers who want ongoing alerts.
    triplet_pro_saved_search_limit: int = int(os.getenv("TRIPLET_PRO_SAVED_SEARCH_LIMIT", "10"))
    triplet_pro_ai_searches_per_month: int = int(os.getenv("TRIPLET_PRO_AI_SEARCHES_PER_MONTH", "100"))
    triplet_pro_max_origin_airports: int = int(os.getenv("TRIPLET_PRO_MAX_ORIGIN_AIRPORTS", "8"))
    triplet_pro_alert_frequencies: str = os.getenv("TRIPLET_PRO_ALERT_FREQUENCIES", "daily,weekly")
    triplet_pro_price_monthly_label: str = os.getenv("TRIPLET_PRO_PRICE_MONTHLY_LABEL", "€6.99/month")
    triplet_pro_price_yearly_label: str = os.getenv("TRIPLET_PRO_PRICE_YEARLY_LABEL", "€49/year")
    # The amounts behind those labels. A saving can only be stated honestly if
    # it is calculated, and a label is a string — set both or Triplet quotes no
    # saving at all rather than a number nobody checked.
    triplet_pro_price_monthly_amount: float | None = (
        float(os.getenv("TRIPLET_PRO_PRICE_MONTHLY_AMOUNT", "6.99"))
        if os.getenv("TRIPLET_PRO_PRICE_MONTHLY_AMOUNT", "6.99")
        else None
    )
    triplet_pro_price_yearly_amount: float | None = (
        float(os.getenv("TRIPLET_PRO_PRICE_YEARLY_AMOUNT", "49"))
        if os.getenv("TRIPLET_PRO_PRICE_YEARLY_AMOUNT", "49")
        else None
    )
    # 7-day trial: enough to experience Pro, capped so it isn't a free summer.
    triplet_trial_duration_days: int = int(os.getenv("TRIPLET_TRIAL_DURATION_DAYS", "7"))
    triplet_trial_ai_searches_total: int = int(os.getenv("TRIPLET_TRIAL_AI_SEARCHES_TOTAL", "15"))
    triplet_trial_saved_search_limit: int = int(os.getenv("TRIPLET_TRIAL_SAVED_SEARCH_LIMIT", "3"))
    triplet_trial_max_origin_airports: int = int(os.getenv("TRIPLET_TRIAL_MAX_ORIGIN_AIRPORTS", "6"))
    triplet_trial_alert_frequencies: str = os.getenv("TRIPLET_TRIAL_ALERT_FREQUENCIES", "daily,weekly")
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
