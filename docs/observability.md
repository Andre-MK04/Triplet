# Observability

Structured logs on stdout, and nothing else required. Every hosting platform
and log collector already understands JSON lines, and Sentry or an
OpenTelemetry exporter can be added later without touching a call site. None of
this needs a paid vendor to work.

## Format

`LOG_FORMAT` picks the output, defaulting to `json` in production and readable
lines elsewhere — so a deployment gets parseable logs without anyone
remembering to ask, and local work stays legible.

Every line carries the request that produced it. `X-Request-ID` is honoured
when a caller sends one and generated otherwise, then attached to every log
line emitted while handling that request, including from code several layers
down that knows nothing about HTTP.

```json
{"ts":"2026-09-02T09:01:15Z","level":"info","logger":"triplet.events",
 "message":"search.completed","requestId":"demo-request-42",
 "event":"search.completed","tripCount":30,"durationMs":3474,
 "provider":"hybrid","staleFares":0,"zeroResults":false}
```

## What is measured

Named events in `app/observability/events.py`, one function per question
someone would actually ask, so the call sites read as statements about the
product rather than as metric plumbing.

| Area | Events |
|---|---|
| Search | `search.completed` (count, latency, provider, cached, stale fares, zero-result flag), `search.provider_failed` |
| AI | `ai.call` (provider, model, latency, tool calls), `ai.budget_exhausted`, `ai.fallback` |
| Pricing | `pricing.observations_recorded`, `pricing.classified` (verdict plus the sample behind it) |
| Conversion | `watch.created`, `watch.verified`, `fare.feedback` |
| Alerts | `alert.run`, `alert.delivery`, `alert.duplicate_prevented` |
| Infrastructure | `dependency.failed`, `job.completed` |

Two are worth watching from the first day: `zeroResults` on searches, which is
the difference between a working product and an empty one; and the ratio of
`watch.verified` to `watch.created`, which says whether the double opt-in is
costing more watches than it protects.

## What is never written

Redaction is applied centrally to every structured field and every message,
not left to call sites — a call site can forget, and the one that forgets is
the one that logs a reset token.

Fields whose names contain `password`, `token`, `secret`, `authorization`,
`cookie`, `api_key`, `credential`, `card`, `cvv`, `iban` or `session` are
replaced wholesale, at any nesting depth. Independently, anything shaped like a
credential is caught in free text: JWTs, `Bearer` values, `sk_`/`pk_`/`whsec_`
provider keys, and `?token=` in a URL — because a secret interpolated into a
message has no field name to match on.

No event takes a user id, email or IP address. Counts, latencies and categories
answer the operational questions; an identifier answers none of them and turns
an ops tool into a surveillance one. AI events never carry the prompt: a travel
request is personal, and cost and latency are what operations needs.

A test asserts each of these, including that no event signature accepts an
identifier.

## Sentry

Entirely optional. Without `SENTRY_DSN` nothing is imported and nothing is
sent. With it, the same redaction is applied through `before_send` rather than
trusting a vendor's defaults to recognise Triplet's token shapes. Tracing is
off; error grouping is the useful part on a free tier.

If the DSN is set but `sentry-sdk` is not installed, Triplet logs a warning and
starts anyway. Missing error reporting is not a reason to refuse traffic.

## Reading the logs

```bash
grep '"event": "search.completed"' log | jq 'select(.zeroResults)'
```

```bash
grep '"event": "alert.delivery"' log | jq 'select(.ok == false)'
```
