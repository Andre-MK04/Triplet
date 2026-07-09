# Triplet — Caching, Security & Scale Plan

## Handoff block (read first)

Triplet: FastAPI + Postgres (`apps/api`, Railway), Next.js (`apps/web`, Vercel),
Travelpayouts as the fare provider (cached indicative data + affiliate marker).
Today every user search calls Travelpayouts **live** and merges with a DB cache
that's written but barely used for serving. This plan flips that: **a scheduled
worker refreshes a deals cache in Postgres; user searches read from the DB and
only call Travelpayouts on a cache miss/stale (read-through)**. It also hardens
the app for **GDPR/EU law** (EU data residency, erasure + export, retention,
cookie disclosure) and lays **scale hooks** (stateless API, indexes, swappable
rate-limit/session stores) without prematurely building 1M-user infra.

Owner decisions locked: DB is currently US/unknown → migrate to an EU region
(Stage 5). Build for today, architect for 1M (no Redis/replicas until traffic
warrants). Owner does dashboard/region steps; sessions do the code.

Status (2026-07-08): code for all stages built + tested (189 API tests green).
Done in code: deals cache + refresher (S1), read-through search (S2), refresher
prune (S3), GDPR erasure + export + account UI (S4), privacy page + retention
job (S5 code), indexes + SCALING.md (S6). EU residency DONE (all Railway
services + DB in EU West / Amsterdam, verified). All periodic work is unified in
ONE entry point, `app/scheduled/tick.py` (hourly): warms the deals cache, runs
due alerts, and runs retention once/day at RETENTION_HOUR_UTC (default 03:00) —
so there is exactly ONE cron service, not three. **Owner action still open**:
repoint the existing hourly `triplet-alerts` cron's start command from
`python -m app.alerts.runner` to `python -m app.scheduled.tick`.

## Chosen approach, and what was rejected

1. **Deals cache = new `cached_round_trips` table**, refreshed by a worker via
   Travelpayouts `city-directions` (one call per origin ≈ N calls/refresh).
   - Rejected: **full origin×destination×date matrix prefetch** — thousands of
     calls per refresh for routes nobody searches; wasteful and rate-limited.
   - Rejected: **cramming round trips into the one-way `flights` table** — a
     round trip is a different shape (bundle price, two dates) and would muddy
     `price_observations`. Keep `flights` for one-way, `cached_round_trips` for
     the deals surface.
2. **Serve = read-through with TTL**: a search reads the cache; if fresh rows
   cover it, return instantly with **zero** provider calls; if stale/missing
   (a specific rare route), call Travelpayouts once, cache, serve.
   - Rejected: **pure scheduled-only** (never call live on user path) — specific
     routes we never pre-cached would always 0-result.
   - Rejected: **keep calling live every search** (today's behaviour) — slow
     (multi-second), couples user traffic to provider rate limits/outages.
3. **EU data residency**: migrate the Railway Postgres + API service to an EU
   region. Rejected for now: moving to a separate managed EU DB (Neon/Supabase)
   — more moving parts; revisit if Railway EU + backups prove insufficient.
4. **Scale**: stateless API (already), hot-path DB indexes, and interfaces for
   rate-limit/session that can swap to Redis later. Rejected: provisioning
   Redis/read-replicas/CDN caching now — real cost + ops with zero users.

## Stages (each ends in something you can SEE)

### Stage 1 — Persisted deals cache + refresher (SEE: DB rows after a CLI refresh)
- **Goal**: a `cached_round_trips` table and a function that fills it from
  `city-directions` per origin, deduped, with `observed_at`/`expires_at`.
- **Where**: `app/db/models.py` (+ alembic migration 0014),
  `app/db/repositories/cached_deals_repository.py`,
  `app/providers/travelpayouts/flight_provider.py` (already has
  `discover_round_trips`), a new `app/deals/refresher.py`.
- **Verify**: `python -m app.deals.refresher` populates rows;
  `SELECT count(*) FROM cached_round_trips` > 0; rows have future dates + prices.
- **Fence**: no search-path changes yet; no scheduling yet; don't touch auth.

### Stage 2 — Read-through search from cache (SEE: a repeat search makes 0 provider calls)
- **Goal**: `FlightSearchService` serves round-trip deals from
  `cached_round_trips` when fresh; only calls Travelpayouts on miss/stale, then
  caches. A freshness TTL (default 24h) decides.
- **Where**: `app/services/flight_search_service.py`,
  `app/services/trip_builder.py` (consume cached fares),
  `app/tools/travel_tools.py`.
- **Verify**: with the cache warm, run the same search twice; a request counter
  / log shows the 2nd made no live Travelpayouts call; results identical.
- **Fence**: keep the existing provider adapters untouched behind the interface;
  don't change scoring or the honesty labels.

### Stage 3 — Scheduled refresh on Railway (SEE: deals auto-refresh; log proves it)
- **Goal**: a Railway cron service runs `python -m app.deals.refresher` on a
  schedule (start every 3h); stale rows pruned.
- **Where**: `apps/api/railway` config note in PLAN; `refresher.py` prune logic.
- **Verify**: cron run logs "refreshed N origins, upserted M deals"; querying
  the API for a common region returns cached rows with recent `observed_at`.
- **Fence**: reuse the existing worker pattern (like the alerts runner); no new
  infra services beyond a cron.

### Stage 4 — GDPR data-subject rights (SEE: user deletes account + downloads their data)
- **Goal**: right to erasure (`DELETE /auth/me` → hard-delete user + cascade
  saved searches, profile, oauth links, sessions, suggestions, audit tied to
  them) and right to access (`GET /me/export` → JSON of everything we hold on
  the user). Account page gets "Download my data" and "Delete my account".
- **Where**: `app/routers/auth.py` or `app/routers/me.py`, a
  `app/privacy/service.py`, `apps/web/app/account/page.tsx`.
- **Verify**: create a user, export → JSON contains profile+searches; delete →
  subsequent `/auth/me` is 401 and the rows are gone from the DB.
- **Fence**: deletion must cascade completely (no orphaned PII); audit the
  deletion itself (action only, no PII). Don't expose other users' data.

### Stage 5 — EU residency + privacy/security hardening (SEE: DB in EU; privacy page live)
- **Goal**: (owner) recreate Railway Postgres + API in an EU region and re-run
  migrations + reseed; (code) a `/privacy` page (what we store, why, retention,
  the Travelpayouts affiliate cookie disclosure), a lightweight cookie/affiliate
  consent note, and a retention cleanup (prune old `audit_events`, expired
  `trip_suggestions`, stale `cached_round_trips`).
- **Where**: Railway dashboard (owner); `apps/web/app/privacy/`,
  `app/privacy/retention.py` (+ cron), README/security docs.
- **Verify**: `/ready` shows EU region host; `/privacy` renders; retention job
  deletes rows older than policy; DB not publicly reachable (private networking).
- **Fence**: don't delete anything a user might still need; retention windows
  documented before enabling deletion.

### Stage 6 — Scale-readiness hooks (SEE: index migration applied; runbook in repo)
- **Goal**: indexes on `cached_round_trips` (origin, destination, observed_at,
  and a composite for the hot query); wrap rate-limit + session lookups behind
  small interfaces with an in-memory impl now and a documented Redis swap;
  a short SCALING.md runbook (when to add pooling/Redis/replicas/CDN).
- **Where**: migration 0015, `app/rate_limit.py`, `SCALING.md`.
- **Verify**: `EXPLAIN` on the hot query uses the index; tests green; runbook
  present with concrete thresholds.
- **Fence**: no behavioural change; do not actually provision Redis/replicas.

## Risks, with tripwires
- **Refresh exceeds Travelpayouts rate/usage** — tripwire: refresher logs
  request counts; if a run nears limits, widen the interval or cut origins.
  Fallback: read-through still serves specifics on demand.
- **Cache makes prices look stale/wrong** — tripwire: every served row keeps
  `observed_at`; UI shows "checked X ago" and "indicative". If ages look old,
  shorten TTL / refresh interval. Never drop the indicative labelling.
- **EU region migration loses data** — tripwire: it's a fresh reference-data DB
  (no real users yet), so migrate before real signups; take a dump first. If
  real users exist later, this becomes a proper migration with downtime window.
- **Deletion leaves orphaned PII** — tripwire: a test asserts zero rows for the
  user across every table after `DELETE /auth/me`; add new user-linked tables to
  that test whenever they're introduced.
- **In-memory rate limit resets per instance at scale** — tripwire: the moment a
  second API instance runs, brute-force limits weaken; that's the signal to
  implement the Redis-backed limiter (interface already in place).
