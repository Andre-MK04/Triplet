# Triplet Deployment & Live-Data Plan

## Handoff block (read this first, future session)

Triplet is a trip-deal finder: FastAPI + Postgres backend (`apps/api`), Next.js
frontend (`apps/web`), provider-agnostic flight data. Travelpayouts is live and
verified (token + affiliate marker in `apps/api/.env`, never committed) — it
serves **indicative cached market prices**, not live availability. All local
work through Phase 3 is committed; 162 API tests green. This plan covers the
two remaining gaps: **deploying publicly** and **adding genuinely live flight
search**. The owner does the account/dashboard steps; sessions do the rest.

## The chosen approach, and what was rejected

- **Web on Vercel, API + Postgres + cron on Railway.** Rejected: a single VPS
  (more control, but the owner would inherit ops work — patching, backups,
  TLS); Render free tier (Postgres expires after 90 days, cold starts hurt
  the first-search experience). Railway is the boring, low-ops middle.
- **Same apex domain for both** (e.g. `triplet.example` + `api.triplet.example`)
  so auth cookies are first-party. Rejected: separate unrelated domains —
  cross-site cookies with `SameSite=None` work in Chrome but are fragile in
  Safari; same-apex avoids the whole class of problem.
- **Live data via Travelpayouts Real-Time Search API, with Duffel as the
  no-approval bridge.** Rejected: Skyscanner (needs partner status we can't
  get yet); scraping (banned by project rules and by terms).

## Stage 1 — GitHub remote (visible endpoint: repo online) ✅ DONE 2026-07-06

Repo: https://github.com/Andre-MK04/Triplet (**public** — owner's choice).
Verified before/at push: full history scanned against every real secret value
from `.env` — zero hits; no `.env` file ever committed. Keep it that way:
the history of a public repo is forever.

## Stage 2 — API + Postgres on Railway (visible: /ready says "ready" on a public URL)

Owner: Railway account, new project, add Postgres, connect the GitHub repo
(root `apps/api`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
Set env vars (values from local `.env` where applicable — paste, never commit):

```
APP_ENV=production            APP_SECRET=<long random, NOT the dev one>
DATABASE_URL=<railway postgres url, postgresql+psycopg://…>
FRONTEND_URL=https://<web domain>        API_PUBLIC_BASE_URL=https://<api domain>
AUTH_COOKIE_SECURE=true       AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=.<apex domain>        ENABLE_DEV_TOOL_ENDPOINTS=false
FLIGHT_PROVIDER=hybrid        LIVE_FLIGHT_PROVIDER=travelpayouts
TRAVELPAYOUTS_API_ENABLED=true  TRAVELPAYOUTS_API_TOKEN=…  TRAVELPAYOUTS_MARKER=…
ALERTS_ENABLED=true           EMAIL_PROVIDER=console   (smtp later)
```

Then, one-off shell: `alembic upgrade head` and
`python -m app.db.seed --no-demo-flights`  ← reference data only, **zero mock fares**.
Verify: `GET /ready` → "ready"; `POST /trips/search` returns trips whose fares
are all `indicative`/`cached`, none `mock`. The API refuses to boot with dev
secrets — if it won't start, read its startup error, it names the bad setting.
Fence: no worker/cron yet.

## Stage 3 — Web on Vercel (visible: the landing page at the real domain)

Owner: Vercel account, import repo, root directory `apps/web`.
Env: `NEXT_PUBLIC_API_BASE_URL=https://<api domain>` (build-time — it is baked
into the CSP connect-src). Attach the apex domain; put the API on
`api.<apex>` (Railway custom domain) so cookies are first-party.
Verify: landing page live; signup → onboarding → discover search works on the
real domain (this exercises CORS + cookies end-to-end); security headers
present (`curl -sI`).
Fence: don't touch billing/SMTP yet.

## Stage 4 — Watch runner + Travelpayouts verification (visible: an alert email; TP dashboard verified)

- Railway cron service on the same repo: schedule `python -m app.alerts.runner`
  hourly. Verify: create a watch with a high budget, run once, delivery row
  appears (console email in logs until SMTP).
- Owner: press "check installation" in Travelpayouts — the Drive script is
  already in the deployed `<head>`, so it should pass now the site is public.
- Owner (later): SMTP/Resend credentials → `EMAIL_PROVIDER=smtp` + SMTP_* vars.

## Stage 5 — Genuinely live flight search (visible: a fare marked "Live fare" in the UI)

Two doors, not mutually exclusive:

1. **Travelpayouts Real-Time Search API** — ❌ closed for now (checked
   2026-07-07): requires ≥50,000 monthly active users, far beyond a new
   product. Tripwire fired as planned → door 2 is the live-fare path.
   Revisit if/when Triplet approaches that scale. If granted someday: build
   `app/providers/travelpayouts/realtime.py` behind the existing interface,
   fares marked `confidenceLevel="live"`, smoke test before use.
2. **Duffel bridge** (works today, no approval): owner creates a duffel.com
   account, sets `DUFFEL_API_ENABLED=true` + `DUFFEL_API_KEY`; the adapter is
   already built and tested. `LIVE_FLIGHT_PROVIDER=duffel` for live prices,
   with Travelpayouts links still used for monetized deep links via hybrid
   merging (higher-confidence fare wins in dedupe).

Until one of these doors opens, honest state: fares are real market prices,
labeled "Indicative", never presented as live. That labeling must not change.

## Risks, with tripwires

- **Cookie/CORS failures cross-domain** — tripwire: login works locally but
  the deployed dashboard shows logged-out. Fix: both services on one apex
  (Stage 3), `AUTH_COOKIE_DOMAIN=.<apex>`; only if a shared apex is impossible,
  switch `AUTH_COOKIE_SAMESITE=none`.
- **TP real-time access refused or slow** — tripwire: no dashboard approval
  within ~2 weeks. Fallback: Duffel bridge (door 2) — decided in advance so
  nobody relitigates it.
- **In-memory rate limits reset per instance** — fine at one Railway replica;
  tripwire is scaling beyond one instance, which needs Redis-backed limits
  first (known TODO, not a Stage 1–5 blocker).
- **Alembic on fresh Postgres** — the chain has only ever run on the dev DB
  and SQLite. Tripwire: `alembic upgrade head` fails in Stage 2's shell —
  fix the migration then, before any data exists; it's cheap on an empty DB.

## Status

- [x] Stage 1 — GitHub remote (public repo, history verified secret-free)
- [x] Stage 2 — API + Postgres live at https://triplet-production.up.railway.app
      (verified 2026-07-06: /ready green, dev tools 404, real search returns
      30 all-indicative trips with affiliate-attributed links, zero mock fares)
- [x] Stage 3 — Web live at https://triplet-web.vercel.app (verified 2026-07-06:
      page serves, Drive snippet in HTML, CSP points at the Railway API, CORS
      preflight passes with credentials for the Vercel origin)
- [ ] Stage 4 — Cron runner + TP verification (+ SMTP later)
- [ ] Stage 5 — Live fares: TP real-time ruled out (50k MAU floor); Duffel is
      the path whenever the owner wants live prices. Until then: indicative
      fares, honestly labeled — a valid steady state.
