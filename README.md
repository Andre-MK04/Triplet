# Triplet

Triplet helps you find cheap trips, not just cheap flights. This MVP finds cheap European trips from multiple nearby airports using mock one-way flights and mock ground transfers so the smart open-jaw trip builder can be developed before real flight APIs are added.

## Project Structure

```text
triplet/
  apps/
    api/
      alembic/    Database migrations
      app/
        db/        SQLAlchemy models, repositories, and seed data
        models/    Pydantic request/response models
        providers/ Flight provider interface and implementations
        routers/   FastAPI routes
        tools/     Internal AI/tool capability layer
        ai/        Rule-based natural-language intent parser placeholder
        mcp/       MCP planning docs and server stub
        services/  Flight search, trip builder, scoring, and explanations
        tests/     Pytest backend tests
    web/            Next.js App Router frontend
  packages/
    shared/         Shared TypeScript types
```

## Backend Setup

```bash
docker compose up -d db

cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional because the app has a local default.
export DATABASE_URL=postgresql+psycopg://triplet:triplet@localhost:5433/triplet
export FLIGHT_PROVIDER=database

alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8001
```

The API exposes:

- `GET /health`
- `GET /airports`
- `POST /trips/search`
- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `GET /auth/me`
- `GET /me/saved-searches`
- `POST /me/saved-searches`

## Database

Local PostgreSQL runs through Docker Compose:

```bash
docker compose up -d db
```

Connection defaults:

```text
APP_NAME=Triplet
APP_ENV=local
DATABASE_URL=postgresql+psycopg://triplet:triplet@localhost:5433/triplet
FLIGHT_PROVIDER=database
ENABLE_DEV_TOOL_ENDPOINTS=true
SKYSCANNER_API_ENABLED=false
SKYSCANNER_API_KEY=
SKYSCANNER_BASE_URL=https://partners.api.skyscanner.net
SKYSCANNER_TIMEOUT_SECONDS=20
SKYSCANNER_MAX_REQUESTS_PER_SEARCH=30
SKYSCANNER_CACHE_ENABLED=true
SKYSCANNER_MARKET=SI
SKYSCANNER_LOCALE=en-GB
SKYSCANNER_CURRENCY=EUR
SKYSCANNER_AFFILIATE_ENABLED=true
SKYSCANNER_MEDIA_PARTNER_ID=
APP_SECRET=dev-secret-change-me
AUTH_ENABLED=true
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=30
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=
AUTH_PASSWORD_MIN_LENGTH=12
AUTH_RATE_LIMIT_WINDOW_SECONDS=300
AUTH_RATE_LIMIT_MAX_ATTEMPTS=20
API_RATE_LIMIT_WINDOW_SECONDS=60
TRIPS_SEARCH_RATE_LIMIT_MAX_ATTEMPTS=60
AI_SEARCH_RATE_LIMIT_MAX_ATTEMPTS=20
PROVIDER_SMOKE_TEST_RATE_LIMIT_MAX_ATTEMPTS=10
API_PUBLIC_BASE_URL=http://localhost:8001
AUTH_PUBLIC_BASE_URL=http://localhost:8001
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
APPLE_OAUTH_CLIENT_ID=
APPLE_OAUTH_CLIENT_SECRET=
APPLE_OAUTH_TEAM_ID=
APPLE_OAUTH_KEY_ID=
APPLE_OAUTH_PRIVATE_KEY=
FRONTEND_URL=http://localhost:3000
```

Run migrations:

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
```

Seed mock travel data:

```bash
python -m app.db.seed
```

The seed script is idempotent and inserts airport areas, airports, mock flights, and ground transfers.

## Accounts And Authentication

Triplet includes backend-managed email/password accounts for the MVP. Passwords are hashed before storage, access tokens and refresh tokens are stored in `httpOnly` cookies, and saved searches can belong to a logged-in user.

The database intentionally stores `users.password_hash`, not the user's raw password. If you inspect the database after signup, you should see a value beginning with `pbkdf2_sha256$...`. You should never see or store the plain password.

Local development defaults:

```text
APP_SECRET=dev-secret-change-me
AUTH_ENABLED=true
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=30
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=
AUTH_PASSWORD_MIN_LENGTH=12
AUTH_RATE_LIMIT_WINDOW_SECONDS=300
AUTH_RATE_LIMIT_MAX_ATTEMPTS=20
FRONTEND_URL=http://localhost:3000
```

Use a strong `APP_SECRET` outside local development. Set `APP_ENV=production` and `AUTH_COOKIE_SECURE=true` when serving the API over HTTPS. The API refuses to start in production if it still uses the default development secret, insecure auth cookies, or non-HTTPS public URLs. `ENVIRONMENT` is still accepted as a legacy fallback.

Account routes:

- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/refresh`
- `GET /auth/me`
- `PATCH /auth/me`
- `POST /auth/change-password`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /auth/oauth/google/start`
- `GET /auth/oauth/apple/start`
- `GET|POST /auth/oauth/{provider}/callback`

OAuth environment variables:

```text
AUTH_PUBLIC_BASE_URL=http://localhost:8001
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
APPLE_OAUTH_CLIENT_ID=
APPLE_OAUTH_CLIENT_SECRET=
APPLE_OAUTH_TEAM_ID=
APPLE_OAUTH_KEY_ID=
APPLE_OAUTH_PRIVATE_KEY=
BILLING_ENABLED=false
BILLING_PROVIDER=stripe
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO_MONTHLY=
STRIPE_PRICE_PRO_YEARLY=
BILLING_SUCCESS_URL=http://localhost:3000/billing/success
BILLING_CANCEL_URL=http://localhost:3000/pricing
BILLING_PORTAL_RETURN_URL=http://localhost:3000/dashboard
TRIPLET_FREE_SAVED_SEARCH_LIMIT=3
TRIPLET_FREE_AI_SEARCHES_PER_DAY=5
TRIPLET_FREE_MAX_ORIGIN_AIRPORTS=6
TRIPLET_FREE_ALERT_FREQUENCIES=daily
TRIPLET_PRO_SAVED_SEARCH_LIMIT=30
TRIPLET_PRO_AI_SEARCHES_PER_DAY=100
TRIPLET_PRO_MAX_ORIGIN_AIRPORTS=12
TRIPLET_PRO_ALERT_FREQUENCIES=daily,weekly
```

Google redirect URI:

```text
http://localhost:8001/auth/oauth/google/callback
```

Apple redirect URI:

```text
http://localhost:8001/auth/oauth/apple/callback
```

OAuth accounts are linked through the `user_oauth_accounts` table. The app stores provider subject IDs and email metadata, not provider access tokens. OAuth-only users get an unusable password marker in `users.password_hash`; they can later set a manual password through the reset-password flow.

Logged-in saved-search routes:

- `GET /me/saved-searches`
- `POST /me/saved-searches`
- `DELETE /me/saved-searches/{id}`
- `POST /me/saved-searches/{id}/preview`
- `POST /me/saved-searches/{id}/run`

The original token-based alert routes under `/alerts` still work for logged-out email alerts. If a browser is logged in and posts to `/alerts`, the saved search is linked to that account while still returning the manage/unsubscribe links.

## Step 9 Billing + Subscriptions

Triplet supports web subscriptions through Stripe for Triplet Pro. Billing is disabled by default in local development, so no Stripe calls are made unless `BILLING_ENABLED=true`.

Billing routes:

- `GET /billing/plans`
- `GET /billing/status`
- `POST /billing/create-checkout-session`
- `POST /billing/create-portal-session`
- `POST /billing/webhook`

Stripe setup:

1. Create a Stripe account and use test mode first.
2. Create a product named `Triplet Pro`.
3. Create two recurring prices: one monthly and one yearly.
4. Copy the price IDs into `STRIPE_PRICE_PRO_MONTHLY` and `STRIPE_PRICE_PRO_YEARLY`.
5. Add `STRIPE_SECRET_KEY`.
6. Add `STRIPE_PUBLISHABLE_KEY` if a future frontend flow needs it.
7. Add a webhook endpoint pointing to `/billing/webhook`.
8. Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`.

Billing environment:

```text
BILLING_ENABLED=false
BILLING_PROVIDER=stripe
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO_MONTHLY=
STRIPE_PRICE_PRO_YEARLY=
BILLING_SUCCESS_URL=http://localhost:3000/billing/success
BILLING_CANCEL_URL=http://localhost:3000/pricing
BILLING_PORTAL_RETURN_URL=http://localhost:3000/dashboard
TRIPLET_FREE_SAVED_SEARCH_LIMIT=3
TRIPLET_FREE_AI_SEARCHES_PER_DAY=5
TRIPLET_FREE_MAX_ORIGIN_AIRPORTS=6
TRIPLET_FREE_ALERT_FREQUENCIES=daily
TRIPLET_PRO_SAVED_SEARCH_LIMIT=30
TRIPLET_PRO_AI_SEARCHES_PER_DAY=100
TRIPLET_PRO_MAX_ORIGIN_AIRPORTS=12
TRIPLET_PRO_ALERT_FREQUENCIES=daily,weekly
```

Local modes:

- Billing disabled: no Stripe calls; billing status returns free plan entitlements.
- Billing enabled: requires Stripe test keys and price IDs; Checkout and Portal sessions can be created.

## Flight Provider Strategy

Triplet is provider-agnostic. All flight data flows through the `FlightProvider` interface
(`search_one_way`, `search_return`, `search_flexible`, `get_provider_status`, `smoke_test`,
`normalize_response_to_internal_flights`), and every fare carries a `confidenceLevel`
(`live` / `cached` / `indicative` / `mock`) plus `observedAt`/`expiresAt` so the UI can always
say "last checked X ago" and never present stale or demo data as live.

**Do not treat live flight search as working until one provider has a successful smoke test
with real credentials.** Without credentials, everything runs on the mock/database providers,
clearly labeled as demo/cached fares.

### Provider Matrix

| Capability | Mock | Database | Duffel | Travelpayouts / Aviasales | Skyscanner | FutureProvider |
| --- | --- | --- | --- | --- | --- | --- |
| Access status | available | available | **not configured** (self-serve signup) | **not configured** (affiliate signup) | requires approval (partner program) | planned |
| One-way search | yes | yes (cached) | yes | yes | yes | — |
| Return search | yes | yes (cached) | yes (two one-ways) | yes | yes (two one-ways) | — |
| Multi-city / open-jaw | no (trip builder composes) | no (trip builder composes) | yes (multi-slice, not mapped yet) | no | no | — |
| Flexible date search | yes | yes | no (per-date requests) | yes (per-month queries) | yes (sampled dates) | — |
| Price history | no | yes (`price_observations`) | no (we record observations) | yes (cached market data) | no | — |
| Deep links | no | cached links | **no** (booking API, no public link) | yes (Aviasales search links) | yes | — |
| Affiliate links | no | cached links | no | yes (`marker` attribution) | yes (media partner ID) | — |
| Baggage info | no | cached flag | yes | no | no | — |
| Live availability | no | **never** | yes | **no — indicative prices only** | yes | — |
| Pricing / rate limits | none | local reads | metered per search request; cap `DUFFEL_MAX_REQUESTS_PER_SEARCH` | generous but cached data; cap `TRAVELPAYOUTS_MAX_REQUESTS_PER_SEARCH` | partner terms; cap `SKYSCANNER_MAX_REQUESTS_PER_SEARCH` | — |
| Required env vars | — | `DATABASE_URL` | `DUFFEL_API_ENABLED`, `DUFFEL_API_KEY` | `TRAVELPAYOUTS_API_ENABLED`, `TRAVELPAYOUTS_API_TOKEN`, `TRAVELPAYOUTS_MARKER` | `SKYSCANNER_API_ENABLED`, `SKYSCANNER_API_KEY`, `SKYSCANNER_MEDIA_PARTNER_ID` | — |
| Implementation status | implemented | implemented | implemented (needs credentials for smoke test) | implemented (needs token for smoke test) | adapter only, dormant | planned |

Notes:

- **Duffel** is the active live-price candidate: self-service API access, real offers with baggage
  data and offer expiry. It is a booking API, so there are no public deep links; in the MVP it is
  a price/availability source and users are sent to a general search link elsewhere.
- **Travelpayouts/Aviasales** is the active affiliate/deep-link candidate: cached market prices
  (`confidenceLevel=indicative`, never shown as live) with attributable Aviasales search links.
- **Skyscanner** stays dormant (`requires_approval`) until partner access exists. The adapter is
  kept so it can be activated by configuration alone.
- The AI layer never invents fares; it only ranks and explains flights returned by these providers.

### Configuring a Real Provider

Keep API keys in the backend environment only. Then:

```text
# Duffel (live offers)
FLIGHT_PROVIDER=hybrid
LIVE_FLIGHT_PROVIDER=duffel
DUFFEL_API_ENABLED=true
DUFFEL_API_KEY=<backend only>

# or Travelpayouts (indicative prices + affiliate links)
FLIGHT_PROVIDER=hybrid
LIVE_FLIGHT_PROVIDER=travelpayouts
TRAVELPAYOUTS_API_ENABLED=true
TRAVELPAYOUTS_API_TOKEN=<backend only>
TRAVELPAYOUTS_MARKER=<affiliate marker>
```

Run the sanitized smoke tests (counts and status only; no secrets, no raw payloads):

```bash
cd apps/api
source .venv/bin/activate
python -m app.providers.duffel.smoke_test --origin VIE --destination ALC
python -m app.providers.travelpayouts.smoke_test --origin VIE --destination ALC
python -m app.providers.skyscanner.smoke_test --origin VIE --destination ALC
```

Provider diagnostics are available only when `ENABLE_DEV_TOOL_ENDPOINTS=true`:

```text
GET /providers/status
GET /providers/smoke-test?provider=duffel&origin=VIE&destination=ALC&maxResults=3
```

Triplet does not sell or book flights. It sends users to provider or partner pages through
deep links or affiliate links, labeled "Check price" / "View deal" — never "Book now".

## Production Readiness

See [docs/deployment.md](docs/deployment.md) for the full checklist.

Minimum production settings:

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
FRONTEND_URL=https://your-frontend-domain
API_PUBLIC_BASE_URL=https://your-api-domain
APP_SECRET=<long random secret>
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
ENABLE_DEV_TOOL_ENDPOINTS=false
```

The API refuses to start in production if the development secret, insecure auth cookies, or non-HTTPS public URLs are configured.

Manual QA before deploy:

- `GET /health` returns `ok`.
- `GET /ready` returns a ready or clearly degraded status without secrets.
- Manual trip search works with database fallback.
- AI search uses the rule-based fallback when `AI_ENABLED=false`.
- Skyscanner smoke test succeeds when real API access is configured.
- Browser responses include `X-Request-ID` and security headers.

For local webhook testing, use the Stripe CLI conceptually to forward events to:

```text
http://localhost:8001/billing/webhook
```

Webhook events handled:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

Free limits:

- 3 saved alerts
- 5 AI searches per day
- 6 origin airports
- Daily alerts

Pro limits:

- 30 saved alerts
- 100 AI searches per day
- 12 origin airports
- Daily and weekly alerts

iOS note: this step implements web Stripe subscriptions only. A future iOS app may require StoreKit / Apple in-app purchases for digital premium features. Do not add Stripe Checkout inside the iOS app without reviewing App Store rules.

## Step 10 Product Flow Polish

Triplet now has a more complete early-product flow across search, onboarding, saved alerts, billing, and account settings.

Pages:

- `/` marketing landing page: animated 3D route globe (SVG fallback on mobile/reduced motion), how-it-works, clearly-labeled demo trip cards, travel-profile preview, deal intelligence, security, pricing teaser.
- `/discover` search page with AI/advanced tabs, airport chips, trip results, and the save-alert flow.
- `/login` and `/signup` dedicated auth pages (email/password + Google OAuth start).
- `/onboarding` animated multi-step travel-profile quiz backed by `/me/travel-profile`.
- `/dashboard` account dashboard with plan summary, usage meters, saved watches (preview, edit, pause, resume, delete), billing, and travel-profile shortcuts.
- `/pricing` Free/Pro pricing with monthly/yearly toggle, limit comparison, and FAQ.
- `/security` plain-language security & privacy overview.
- `/dev/providers` development-only provider status + smoke-test page (hidden when dev tool endpoints are disabled).
- `/billing/success`, `/billing/cancel` Stripe checkout result pages.
- `/account` profile, password, billing, and logout settings.
- `/reset-password` request + complete password reset.

Dashboard features:

- Current plan and subscription status.
- Saved alert usage and AI search usage.
- Saved alert cards showing dates, airports, budget, frequency, last checked, last notified, and best price seen.
- Edit saved alert name, airports, date range, budget, and frequency.
- Pause, resume, delete, and preview saved alerts.

Provider/demo messaging:

- Database mode is presented as demo/cached fares.
- Hybrid fallback warnings are shown when live provider data is unavailable.
- Results remain usable in local development without live provider credentials.

Manual QA checklist:

Logged out:

- Open `/`.
- Try an example AI prompt.
- Switch to Advanced search and run a structured search.
- Save an email alert.
- Open `/pricing`.
- Sign up or log in.

Logged in Free:

- Save an alert from search results.
- Open `/dashboard`.
- Preview an alert.
- Edit alert budget/name/date/frequency.
- Pause, resume, and delete an alert.
- Try exceeding the saved-alert limit.
- Open `/pricing` and start checkout if billing is enabled.

Logged in Pro:

- Dashboard should show Pro plan and higher limits.
- Billing card should show Manage billing when a Stripe customer exists.

Provider:

- `FLIGHT_PROVIDER=database` should show demo/cached fare messaging.
- Hybrid fallback should show cached-fare warning.
- No-results state should suggest widening budget, dates, or transfer limits.

### Database Troubleshooting

If Docker commands return:

```text
Cannot connect to the Docker daemon ... Is the docker daemon running?
```

start Docker Desktop first, wait until it says Docker is running, then retry:

```bash
docker compose up -d db
```

If you do not want to use Docker for local MVP development, you can temporarily use SQLite:

```bash
cd apps/api
source .venv/bin/activate
export DATABASE_URL=sqlite:///./triplet.db
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --port 8001
```

SQLite is only a local fallback. PostgreSQL remains the intended development database.

If the backend returns:

```text
role "triplet" does not exist
```

then Alembic is probably reaching a different local PostgreSQL server. Triplet maps its Docker database to host port `5433` to avoid colliding with a local Postgres on `5432`. Recreate the local project database:

```bash
docker compose down -v
docker compose up -d db

cd apps/api
source .venv/bin/activate
alembic upgrade head
python -m app.db.seed
```

Then restart FastAPI:

```bash
uvicorn app.main:app --reload --port 8001
```

If you previously ran the app using the old local database name, you may need to reset the old Docker volume or manually create/migrate the new `triplet` database. Do not delete Docker volumes unless you are comfortable losing local development data.

## Flight Providers

Trip search now reads flights through a provider abstraction:

```text
/trips/search
  -> FlightSearchService
  -> FlightProvider
  -> Trip Builder
```

Available provider names:

- `database`: default. Reads seeded or cached flights from PostgreSQL through `DatabaseFlightProvider`.
- `duffel`: live offers through `DuffelFlightProvider` (requires `DUFFEL_API_KEY`).
- `travelpayouts`: indicative cached prices and affiliate links through `TravelpayoutsAviasalesProvider` (requires `TRAVELPAYOUTS_API_TOKEN`).
- `skyscanner`: dormant `SkyscannerFlightProvider`; requires partner approval.
- `hybrid`: reads cached/database fares and tries the provider named by `LIVE_FLIGHT_PROVIDER` for fresh fares, falling back to database if it is unavailable.
- `mock`: available for unit tests and local service-level experiments.

The trip builder is provider-agnostic. External flight APIs can be added later by normalizing their results into the internal `Flight` model without changing scoring, explanations, or frontend response models.

Provider modes:

```bash
# Seeded/cached database fares only
FLIGHT_PROVIDER=database uvicorn app.main:app --reload --port 8001

# Database fares plus a live provider when available. Falls back to database.
FLIGHT_PROVIDER=hybrid LIVE_FLIGHT_PROVIDER=duffel uvicorn app.main:app --reload --port 8001
```

Diagnostics, when development tool endpoints are enabled:

```bash
curl http://localhost:8001/providers/status
curl "http://localhost:8001/providers/smoke-test?provider=duffel&origin=VIE&destination=ALC&maxResults=3"
```

Every live/indicative fare fetched from a provider is also recorded in the `price_observations`
table, building the price history that deal scoring will compare against.

Provider metadata is included in trip search responses:

```json
{
  "providerMetadata": {
    "providerUsed": "hybrid",
    "liveProviderAttempted": true,
    "liveProviderSucceeded": false,
    "cachedResultsUsed": true,
    "providerName": "skyscanner",
    "requestsAttempted": 12,
    "requestsLimit": 30,
    "rawOffersCount": 3,
    "mappedFlightsCount": 2,
    "skippedOffersCount": 1,
    "affiliateLinksGenerated": 0,
    "deepLinksReturned": 2,
    "providerWarnings": []
  }
}
```

## Provider QA Checklist

Database mode:

```bash
FLIGHT_PROVIDER=database uvicorn app.main:app --reload --port 8001
```

Check:

```bash
curl http://localhost:8001/providers/status
curl "http://localhost:8001/providers/smoke-test?origin=VIE&destination=ALC&departureDate=2026-08-15&maxResults=3"
```

Expected: database available and cached flights present.

Hybrid mode without live provider credentials:

```bash
FLIGHT_PROVIDER=hybrid LIVE_FLIGHT_PROVIDER=duffel DUFFEL_API_ENABLED=false uvicorn app.main:app --reload --port 8001
```

Expected: app still works, live provider warning is returned, database fallback is used.

Live provider mode without credentials:

```bash
FLIGHT_PROVIDER=duffel DUFFEL_API_ENABLED=true DUFFEL_API_KEY= uvicorn app.main:app --reload --port 8001
```

Expected: clean error, no crash, no secrets exposed.

Live provider mode with credentials (any of duffel / travelpayouts / skyscanner):

```bash
FLIGHT_PROVIDER=hybrid \
LIVE_FLIGHT_PROVIDER=duffel \
DUFFEL_API_ENABLED=true \
DUFFEL_API_KEY=your_backend_key \
uvicorn app.main:app --reload --port 8001
```

Expected: smoke-test shows `apiOk=true` or a controlled API warning; `mappedFlightsCount` is visible; cached/database fallback stays available; no keys or raw provider payloads are exposed.

## Internal Tools And AI Search

Triplet now has an internal tools layer:

```text
Frontend
  -> FastAPI backend
  -> Internal Tool Registry
     -> search_trips
     -> get_airports
     -> estimate_ground_transfer
     -> explain_trip
     -> parse_trip_intent
  -> deterministic services and database
```

The core backend services still perform deterministic trip generation. Internal tools expose those backend capabilities in a stable way so the AI orchestrator and future MCP server can call them without changing the trip builder.

Development tool endpoints are guarded by:

```text
ENABLE_DEV_TOOL_ENDPOINTS=true
```

Do not enable development tool endpoints in production.

List tools:

```bash
curl http://localhost:8001/tools
```

Run a tool locally:

```bash
curl -X POST http://localhost:8001/tools/run \
  -H "Content-Type: application/json" \
  -d '{
    "toolName": "search_trips",
    "input": {
      "originAirports": ["VIE", "ZAG", "TRS"],
      "startDate": "2026-07-01",
      "endDate": "2026-08-31",
      "minTripLengthDays": 4,
      "maxTripLengthDays": 8,
      "maxBudget": 180,
      "maxGroundTransferHours": 4,
      "tripStyle": "surprise me"
    }
  }'
```

### Step 6 Natural-Language AI Search

AI is disabled by default, so local development is free and does not call any AI provider.
Both OpenAI and Anthropic are supported through the same guarded tool-calling contract.

Configuration:

```text
AI_ENABLED=false
# openai or anthropic
AI_PROVIDER=openai
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5
ANTHROPIC_MAX_TOKENS=1024
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TEMPERATURE=0.2
OPENAI_REASONING_EFFORT=low
AI_MAX_TOOL_CALLS=3
AI_REQUIRE_TOOL_RESULTS=true
AI_MAX_TRIPS_SENT_TO_MODEL=8
AI_MAX_INPUT_TOKENS_HINT=12000
AI_DAILY_REQUEST_LIMIT_PLACEHOLDER=100
```

`gpt-5.4-mini` is the default OpenAI model because it gives better natural-language parsing, tool-calling, and explanation quality than nano while staying much cheaper than the full model. To reduce costs further later, set `OPENAI_MODEL=gpt-5.4-nano`. Do not use the full `gpt-5.4` model by default.

AI disabled mode:

- Uses the rule-based parser.
- Does not need `OPENAI_API_KEY`.
- Never calls OpenAI.
- Good for local development.

AI enabled mode:

- Requires `AI_ENABLED=true` and `OPENAI_API_KEY`.
- Uses `OPENAI_MODEL`, defaulting to `gpt-5.4-mini`.
- Allows the model to call only selected internal tools.
- Enforces `AI_MAX_TOOL_CALLS`.
- Sends compact trip summaries only, capped by `AI_MAX_TRIPS_SENT_TO_MODEL`.
- Does not send raw Skyscanner responses or full provider payloads to the model.
- Keeps trip results sourced from deterministic `search_trips`, not model-generated text.

Local without AI:

```bash
AI_ENABLED=false uvicorn app.main:app --reload --port 8001
```

Local with AI:

```bash
AI_ENABLED=true \
OPENAI_API_KEY=your_key \
uvicorn app.main:app --reload --port 8001
```

Natural-language search:

```bash
curl -X POST http://localhost:8001/ai/search \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find me a cheap 5 to 7 day trip in August from Vienna or Zagreb under 180 euros. I like two-city trips."
  }'
```

Expected response includes:

- `message`: AI or fallback explanation.
- `parsedRequest`: the actual structured search request.
- `trips`: deterministic trip options from `search_trips`.
- `providerMetadata`: provider/cache/live-search details.
- `aiMetadata`: provider, model, tool calls used, fallback flag, and warnings.

Parse only:

```bash
curl -X POST http://localhost:8001/ai/parse \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find me a cheap 5 to 7 day trip in August from Vienna or Zagreb under 180 euros. I like two cities."
  }'
```

Compatibility parse preview:

```bash
curl -X POST http://localhost:8001/ai/parse-trip-intent \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find me a cheap 5 to 7 day trip in August from Vienna or Zagreb under 180 euros. I like two cities."
  }'
```

Search preview with parsed intent:

```bash
curl -X POST http://localhost:8001/ai/search-preview \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find me a cheap 5 to 7 day trip in July from Vienna or Zagreb under 180 euros. I like two cities."
  }'
```

When `AI_ENABLED=false`, `/ai/search` and `/ai/parse` use the rule-based parser fallback. When `AI_ENABLED=true`, OpenAI is attempted first and the backend falls back to rule-based parsing if the provider fails.

## Step 7 Saved Searches And Alerts

Triplet can save a trip search and check it later with the deterministic `search_trips` tool. Alerts do not depend on OpenAI.

Environment variables:

```text
APP_SECRET=dev-secret-change-me
ALERTS_ENABLED=false
ALERTS_DEFAULT_FREQUENCY=daily
ALERTS_MAX_RESULTS_PER_EMAIL=5
ALERTS_MIN_HOURS_BETWEEN_NOTIFICATIONS=24
ALERTS_PUBLIC_BASE_URL=http://localhost:3000

EMAIL_PROVIDER=console
EMAIL_FROM=alerts@triplet.local
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
```

By default, emails are printed/logged by the backend. Real SMTP sending only happens when `EMAIL_PROVIDER=smtp` and SMTP config is set.

Create an alert:

```bash
curl -X POST http://localhost:8001/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "email": "traveler@example.com",
    "name": "July Spain ideas",
    "originAirports": ["VIE", "ZAG"],
    "startDate": "2026-07-01",
    "endDate": "2026-07-31",
    "minTripLengthDays": 5,
    "maxTripLengthDays": 7,
    "maxBudget": 180,
    "maxGroundTransferHours": 4,
    "tripStyle": "two nearby cities",
    "frequency": "daily"
  }'
```

The create response returns one-time manage and unsubscribe URLs. The database stores only token hashes.

Preview an alert:

```bash
curl -X POST "http://localhost:8001/alerts/{id}/preview?token={manage_token}"
```

Run one alert:

```bash
curl -X POST "http://localhost:8001/alerts/{id}/run?token={manage_token}"
```

Run due alerts manually:

```bash
cd apps/api
source .venv/bin/activate
python -m app.alerts.runner
```

Or through the development-only endpoint:

```bash
curl -X POST http://localhost:8001/alerts/run-due
```

Alert notifications are throttled. The runner sends when matching trips are found for the first time, or when the best price improves by at least EUR 10, while respecting `ALERTS_MIN_HOURS_BETWEEN_NOTIFICATIONS`.

## Future MCP Layer

`apps/api/app/mcp/README.md` documents the planned `triplet-travel-mcp` server. MCP will not replace the backend; it will expose selected internal tools to MCP-compatible agents. The deterministic trip builder remains the source of truth, and future user-specific or action tools will require authentication, authorization, and explicit user confirmation.

## Run the Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3001`. The frontend calls `POST http://localhost:8001/trips/search`.

If you need a different backend URL, start the frontend with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 npm run dev
```

## Run Backend Tests

```bash
cd apps/api
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Trip Builder

The backend builds trips from database-backed one-way flights and ground transfers. It filters outbound flights by selected origin airports and date range, then pairs each outbound with valid return flights whose destination is one of the selected origin airports.

Trip length is calculated as nights from the outbound arrival date to the return departure date. A trip where the return departs on or before the outbound arrival date is rejected.

Two trip types are supported:

- Same-city trips, where the outbound destination and return departure airport are the same or belong to the same airport area, such as `VCE` and `TSF` for Venice.
- Open-jaw trips, where the outbound city and return city are connected by a known mock ground transfer within the user's max transfer time.

Each trip totals flight prices plus any ground-transfer cost, filters by budget, and generates warnings and tags. Trips receive two explainable rule-based scores from 0 to 100, each with a per-factor breakdown in the API response:

- **DealScore** — price/quality independent of taste: budget headroom, flight times, transfer effort, stops, baggage, fare confidence, and (once `price_observations` has at least 3 samples for a route) the price versus the route's observed baseline.
- **FitScore** — match against the searcher's saved travel profile: origin airports, preferred trip length and months, comfort rules, open-jaw willingness, and budget comfort zone. Without a profile, a request-only fit is used.

Results are sorted by deal score, fit score, price, and shorter ground transfer. The top results of every search are persisted as trip suggestions (7-day TTL) and served by `GET /trips/suggestions/{id}`; suggestions created by a logged-in user are private to that user. The saved-watch runner passes the watch owner through the same path, so alert results are profile-aware too.

## Known Limitations

- All flights and transfers are mock data.
- `directOnly` is accepted in the request model, but every mock flight is currently treated as direct.
- Ground transfers are static city/airport pairs, not live train or bus schedules.
- Repository tests use SQLite in memory; local development uses PostgreSQL.
- Provider tests (Duffel, Travelpayouts, Skyscanner) use mocked HTTP responses; no real external API calls run in tests.
- Duffel and Travelpayouts adapters are implemented but not smoke-tested against live APIs yet: no credentials are configured. Do not treat live search as working until a smoke test passes.
- Duffel offers have no public deep link (it is a booking API); Travelpayouts prices are indicative, never live.
- Skyscanner mapping supports direct one-way offers and simple single-itinerary connections; complex multi-itinerary offers may be skipped. The adapter is dormant pending partner approval.
- AI is optional. OpenAI is called only when `AI_ENABLED=true`; otherwise rule-based fallback is used.
- Alert emails are console/log output by default.
- MCP is documentation and a stub only; no production MCP server is exposed.
- No booking, scraping, or production email provider integration is included yet.

## Next Step

Obtain Duffel and/or Travelpayouts credentials and run the provider smoke tests, then build the
frontend shell (landing, onboarding quiz, discover/results/detail pages) on top of the existing API.
