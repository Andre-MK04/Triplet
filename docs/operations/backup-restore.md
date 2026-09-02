# Database backup and restore

**Read this before inviting real users.** Right now Triplet's data exists in
one PostgreSQL database on Railway, and this repository contains no backup
automation of its own.

That sentence is the point of this document. Everything below distinguishes
what Triplet implements from what the hosting provider must be configured to
do — because the most common way to lose data is to assume someone else's
system was already handling it.

---

## What Triplet implements

| Concern | Status |
|---|---|
| Schema migrations, forward and reversible | Alembic, verified in CI against PostgreSQL |
| Scheduled cleanup of expired rows | `app/scheduled/tick.py`, hourly |
| GDPR erasure of one account's data | `DELETE /auth/me`, `app/privacy/service.py` |
| GDPR export of one account's data | `GET /me/export` |
| **Database backups** | **None. This is the provider's job — see below.** |
| **Restore tooling** | **None. The procedure below is manual and deliberate.** |

Triplet does not back itself up, and no code in this repository will notice if
backups stop happening. Verifying that is a standing operational task, not
something the application can assert.

---

## What must be configured on the host

Triplet runs on Railway with a managed PostgreSQL instance. **Confirm each of
these in the Railway dashboard — do not assume any of them.**

- [ ] Automated backups are enabled for the production database.
- [ ] The schedule is at least daily.
- [ ] Retention is at least 7 days; 30 is better while the product is young.
- [ ] Point-in-time recovery is enabled if the plan offers it. Daily snapshots
      alone mean a bad afternoon costs up to a day of accounts and watches.
- [ ] You know how to trigger a manual backup, and have done it once.
- [ ] You know where backups are stored and who can read them. A backup is a
      complete copy of every user's data; it deserves the access controls the
      live database has.
- [ ] Backup storage is in the EU, matching the database's own residency.

If Railway's plan does not provide automated backups, that is a launch blocker,
not a nice-to-have. The fallback is a scheduled `pg_dump` to object storage,
which is more moving parts and more ways to fail quietly.

---

## What is in the database, and what it would cost to lose

Not all of it is equally replaceable. This ranking is what a restore should be
checked against.

### Irreplaceable — lost forever if the database is lost

- `users`, `user_oauth_accounts` — accounts, password hashes, verification
  state, legal acceptance records
- `user_travel_profiles` — everything someone told Triplet about how they travel
- `saved_searches` — watches, including the confirmations people gave
- `user_countries`, `country_visits` — a personal travel history that exists
  nowhere else and cannot be reconstructed
- `billing_subscriptions`, `billing_events` — reconcilable against Stripe, but
  painfully
- `audit_events` — the security record, which is worth most precisely when
  something has gone wrong

### Expensive to lose, rebuildable over time

- `price_observations` — the long-run fare history the product's price context
  is built on. Rebuilding means waiting months for observations to accumulate.
- `fare_feedback` — reliability reports from travellers, which cannot be asked
  for again

### Cheap to lose — rebuilt automatically

- `cached_round_trips`, `featured_deal_snapshots` — caches, refilled by the
  hourly job
- `trip_suggestions` — expiring by design
- `email_verification_tokens`, `password_reset_tokens` — short-lived; losing
  them costs people one "send another link"
- `search_logs`, `usage_counters` — operational counters
- `airports`, `locations`, `airport_directory`, `airport_areas` — public
  reference data, re-importable with `python -m app.db.seed --directories`

---

## Before a destructive migration

A migration that drops a column or rewrites data is the most likely reason
you will ever need a backup.

1. Take a manual backup and **confirm it completed**, rather than assuming the
   nightly one is recent enough.
2. Note the current revision: `alembic current`.
3. Apply the migration to a restored copy first, using the procedure below.
4. Only then apply it to production.

---

## Restoring

Never restore over production as a first move. Restore beside it, confirm the
data is what you expect, and only then decide.

1. **Create an isolated database.** A separate Railway service, or a local
   PostgreSQL — never the production instance.

2. **Restore the backup into it.**

   ```bash
   pg_restore --clean --if-exists --no-owner --dbname "$RESTORE_DATABASE_URL" backup.dump
   ```

3. **Check the schema version matches the code you intend to run.**

   ```bash
   DATABASE_URL="$RESTORE_DATABASE_URL" alembic current
   ```

   A backup older than a migration needs `alembic upgrade head` before the API
   will start against it.

4. **Check the tables that cannot be rebuilt.** Row counts, not vibes:

   ```bash
   psql "$RESTORE_DATABASE_URL" -c "select
     (select count(*) from users) as users,
     (select count(*) from saved_searches) as watches,
     (select count(*) from user_travel_profiles) as profiles,
     (select count(*) from user_countries) as travel_map,
     (select count(*) from price_observations) as fare_history;"
   ```

   Compare against what production reported before the incident. A restore that
   silently lost a table is worse than a failed one, because it looks fine.

5. **Start the API against the restored database, in isolation.** Not pointed
   at production's Redis, and not with production's email provider — a restored
   copy running the alerts job would email real people about a stale world.

   ```bash
   DATABASE_URL="$RESTORE_DATABASE_URL" EMAIL_PROVIDER=console \
     python -m uvicorn app.main:app --port 8002
   ```

6. **Exercise the paths that prove the data is intact**, not just present:
   - log in as a known account
   - load its travel profile
   - list its watches, and confirm the verified ones are still verified
   - open the travel map

7. **Only then** promote the restore, and expect to reconcile anything written
   to production after the backup was taken.

---

## A backup nobody has restored is not a backup

It is a file you believe in.

Do a real restore test **before inviting real users**, and periodically
afterwards — quarterly is a reasonable cadence for a product this size. The
test is the procedure above, run against a genuine backup, ending at step 6.

Record when you last did it. If the answer is "never" or "I don't remember",
the honest position is that Triplet does not have verified backups.

---

## What this repository will not do for you

- It will not create backups.
- It will not alert you when a backup fails.
- It will not stop a destructive migration if no recent backup exists.
- It will never run a production restore automatically. Restoring is a decision
  someone makes with the facts in front of them, not something a script infers.
