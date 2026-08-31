# Purging the development database from Git history

## What happened

`apps/api/triplet.db` was committed in `86912f5` (Redesign Stage 2) and remained
tracked until it was removed in the production-hardening pass. The repository is
public, so the file was readable by anyone for that period.

## What it contained

Checked before removal, without extracting contents:

| Table | Rows | Assessment |
|---|---|---|
| `users` | 2 | **Both on test domains** (`@example.com`). No real addresses. |
| `refresh_token_sessions` | 2 | Hashed tokens, for those test accounts. |
| `audit_events` | 3 | Development activity. |
| `trip_suggestions` | 12 | Generated trip payloads, no personal data. |
| `saved_searches` | 0 | Empty. |
| `user_oauth_accounts` | 0 | Empty. |
| Reference data | ~18k | Airports, locations, cached fares — public reference data. |

Passwords were stored hashed (`pbkdf2_sha256`), never plaintext.

**Conclusion: no real user personal data was exposed.** No breach notification
obligation arises from this file. History cleanup is hygiene, not remediation.

## Is history cleanup required?

**No, but it is recommended** — the file is ~4.5 MB and sits in every clone.
Removing it shrinks the repository and removes the dev credentials entirely.

This is deliberately **not automated**: rewriting history changes every commit
SHA after `86912f5`, which breaks existing clones, open pull requests and any
tag or deployment pinned to a rewritten SHA. Do it consciously.

## How to purge it, when you choose to

Requires [`git-filter-repo`](https://github.com/newren/git-filter-repo)
(`brew install git-filter-repo`). Do this on a fresh clone.

```bash
git clone --mirror https://github.com/Andre-MK04/Triplet.git triplet-mirror
cd triplet-mirror
git filter-repo --path apps/api/triplet.db --invert-paths
git push --force
```

Afterwards:

1. Tell every collaborator to re-clone. Old clones cannot be merged cleanly.
2. Rotate anything that was in the file. Here that is only the two test accounts,
   whose sessions should be revoked for tidiness.
3. Check that no deployment references a pre-rewrite commit SHA.

## Preventing a recurrence

`.gitignore` now covers `*.db`, `*.sqlite`, `*.sqlite3` and the SQLite WAL/SHM
sidecars. A fixture that genuinely needs tracking can be whitelisted under
`apps/api/app/tests/fixtures/`.

Run this before any commit that might touch one:

```bash
git ls-files | grep -iE '\.(db|sqlite3?)(-shm|-wal)?$'
```

It should print nothing.
