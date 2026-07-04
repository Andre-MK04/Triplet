# Triplet Deployment

This document is the production-readiness checklist for the Triplet MVP.

## Environment Files

Use template files as references only. Do not commit real `.env` files.

- `apps/api/.env.local.example`: local development with database/demo fares by default.
- `apps/api/.env.staging.example`: staging over HTTPS, usually with hybrid provider mode.
- `apps/api/.env.production.example`: production placeholders, HTTPS URLs, secure cookies, and Skyscanner settings.
- `apps/web/.env*.example`: frontend public API URL only.

Local development remains free when:

```text
AI_ENABLED=false
FLIGHT_PROVIDER=database
SKYSCANNER_API_ENABLED=false
```

## Required Production Settings

Set these before deploying with `APP_ENV=production`:

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
FRONTEND_URL=https://your-frontend-domain
API_PUBLIC_BASE_URL=https://your-api-domain
APP_SECRET=<long random secret>
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
```

The API refuses to start in production if the development secret, insecure cookies, or non-HTTPS public URLs are still configured.

If `AI_ENABLED=true`, set `OPENAI_API_KEY`. The default model is `gpt-5.4-mini`.

If `FLIGHT_PROVIDER=skyscanner`, set `SKYSCANNER_API_ENABLED=true` and `SKYSCANNER_API_KEY`.

If `FLIGHT_PROVIDER=hybrid`, the app will try Skyscanner and fall back to cached/database fares if the live provider is unavailable.

## Skyscanner Setup

Skyscanner Travel API access requires partner approval or a commercial agreement. Keep the API key only in the backend runtime environment.

```text
FLIGHT_PROVIDER=hybrid
SKYSCANNER_API_ENABLED=true
SKYSCANNER_API_KEY=<backend only>
SKYSCANNER_BASE_URL=https://partners.api.skyscanner.net
SKYSCANNER_MARKET=SI
SKYSCANNER_LOCALE=en-GB
SKYSCANNER_CURRENCY=EUR
```

Skyscanner affiliate/referral links can work separately from live API access:

```text
SKYSCANNER_AFFILIATE_ENABLED=true
SKYSCANNER_MEDIA_PARTNER_ID=<partner id>
SKYSCANNER_AFFILIATE_BASE_URL=https://skyscanner.net/g/referrals/v1
```

Triplet does not sell or book flights. It discovers trip options and sends users to Skyscanner or partner pages through provider deep links or affiliate referral links.

Run the sanitized smoke test:

```bash
cd apps/api
source .venv/bin/activate
python -m app.providers.skyscanner.smoke_test --origin VIE --destination ALC --date 2026-08-15 --max-results 3
```

The smoke test reports configuration, API status, mapping counts, and link availability. It does not print API keys or raw provider payloads.

## Health Checks

- `GET /health`: process is running.
- `GET /health/db`: database connectivity only.
- `GET /ready`: database, provider configuration, and AI configuration summary.

`/ready` does not call OpenAI or Skyscanner and does not expose secrets.

## Diagnostics

Provider diagnostics are disabled unless:

```text
ENABLE_DEV_TOOL_ENDPOINTS=true
```

Smoke endpoint:

```text
GET /providers/smoke-test?origin=VIE&destination=ALC&departureDate=2026-08-15&maxResults=3
```

Keep diagnostics disabled in production unless you explicitly need a temporary operational check.

## Security Checklist

- Use HTTPS for frontend and API.
- Use a long random `APP_SECRET`.
- Keep `.env`, `.env.local`, and provider secrets out of git.
- Keep `SKYSCANNER_API_KEY` backend-only.
- Use `AUTH_COOKIE_SECURE=true` in production.
- Use `AUTH_COOKIE_SAMESITE=none` only with secure cookies.
- Keep CORS restricted to the real frontend URL.
- Keep provider diagnostics disabled by default.
- Configure rate limits for auth, AI search, trip search, and provider diagnostics.
- Do not log provider secrets or raw provider payloads.

## Manual QA

1. `GET /health` returns `{"status":"ok"}`.
2. `GET /ready` returns `status=ready` or a clearly explained degraded state.
3. Signup/login works and stores only password hashes.
4. Manual trip search works with `FLIGHT_PROVIDER=database`.
5. AI search works with `AI_ENABLED=false` using the rule-based fallback.
6. AI search works with `AI_ENABLED=true` only when `OPENAI_API_KEY` is set.
7. Hybrid search returns cached/database fares if Skyscanner is unavailable.
8. Skyscanner smoke test reports live search status when valid API access is present.
9. Affiliate fallback links are generated when `SKYSCANNER_MEDIA_PARTNER_ID` is set.
10. Frontend uses only `NEXT_PUBLIC_API_BASE_URL` for the backend URL.
11. Browser responses include `X-Request-ID` and security headers.
