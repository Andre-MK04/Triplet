# Triplet Scaling Runbook

How Triplet scales from today (~0 users) toward 50k and ~1M monthly users, and
the concrete thresholds that trigger each step. Principle: **build for today,
keep the path to 1M open** — don't provision idle heavy infra.

## What's already scale-ready
- **Stateless API.** No in-process user state beyond a short-lived rate-limit
  map, so the API scales horizontally (add Railway replicas) without code change.
- **Read-through deals cache.** User searches read `cached_round_trips` from
  Postgres; the provider is called only on cache miss/stale. User traffic is
  decoupled from Travelpayouts rate limits and latency.
- **Scheduled refresh + retention.** `app/deals/refresher.py` warms the cache on
  a cron; `app/privacy/retention.py` prunes old data. Provider calls scale with
  the number of origins, not with user traffic.
- **Hot-path indexes.** `cached_round_trips` is indexed on `origin_code`,
  `destination_code`, `observed_at`, and a composite `(origin_code, observed_at)`
  for the "fresh deals from these origins" query.
- **Frontend on Vercel's edge/CDN.** Static assets and SSR scale automatically.

## Thresholds → actions (do each only when its tripwire fires)

| Signal | Action |
| --- | --- |
| Login/search p95 latency rising, or >1 API replica | Move rate limiting + session lookups to **Redis** (interface is isolated in `app/rate_limit.py`; swap the store, keep the callers). In-memory limits weaken across replicas — this is the trigger. |
| DB connections near the Postgres limit | Add **PgBouncer / Railway connection pooling** in front of Postgres. |
| Read query load dominates | Add a **Postgres read replica**; point search reads (cache) at the replica, writes at primary. |
| Refresher nears Travelpayouts usage limits | Widen the refresh interval, shard origins across runs, or upgrade the Travelpayouts plan. Read-through still covers on-demand routes. |
| Deals cache table large / slow | Partition or TTL-prune more aggressively (shorten `CACHED_DEALS_RETENTION_DAYS`); the unique route+dates key already bounds row count. |
| Global users, latency-sensitive | Add CDN caching for read-only deal endpoints; consider a second region + geo-routing (revisit EU-only data residency implications first). |

## Cost posture
At ~0–50k MAU a single API instance + one Postgres + one cron is sufficient and
cheap. Redis, replicas, and pooling are added **only** when their tripwire fires,
so we don't pay for or operate idle 1M-scale infrastructure early.

## Non-negotiables at every scale
- User data stays in the **EU/EEA**, encrypted at rest, private-networked.
- Prices stay **labelled indicative**, never presented as guaranteed/live.
- Erasure and export (`DELETE /auth/me`, `GET /me/export`) must keep working and
  must cover every new user-linked table (see `app/privacy/service.py`).
