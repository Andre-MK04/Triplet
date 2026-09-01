# Continuous integration

`.github/workflows/ci.yml` runs on every pull request and every push to `main`.

## Jobs

**Backend** — installs pinned dependencies, runs the pytest suite, applies every
migration from an empty PostgreSQL database, and asserts there is exactly one
migration head. The migration steps guard the failure that is invisible until
deploy: a migration that imports fine, passes review, and then breaks against a
real database. The single-head check catches the classic merge accident where
two branches each add a head and the next deploy refuses to run.

The test suite builds its schema from metadata against in-memory SQLite and
cannot reach a live provider — `conftest.py` pins every provider off — so a CI
run can never spend API credit or hit a real flight API.

**Frontend** — typecheck, vitest, and a production build.

There is no lint step. `next lint` was removed in Next 16 and this repo has no
ESLint configuration or dependency, so the `lint` script could never run and has
been removed rather than left to fail on contact. TypeScript in strict mode is
the static gate. Adding ESLint later is reasonable; doing it as part of a
security pass would have meant either a linter with no config or several hundred
findings nobody had triaged.

**Dependency audit** — `pip-audit` and `npm audit`. Marked `continue-on-error`
on purpose: a CVE published in a transitive dependency overnight should tell us,
not block an unrelated fix from merging. **Read it anyway.** When this job first
ran it found 30 known vulnerabilities across five packages, including nine in
PyJWT, which signs Triplet's session tokens. Those are fixed; the audit is clean
as of the commit that added it.

**Secret and database scan** — fails the build if any `.db`/`.sqlite` file or a
non-example `.env` is tracked. `apps/api/triplet.db` was tracked in this public
repository until September 2026; this is the check that stops it coming back.

## Running the same checks locally

```bash
cd apps/api && python -m pytest -q && python -m alembic upgrade head
```

```bash
cd apps/web && npx tsc --noEmit && npm test && npm run build
```

```bash
cd apps/api && pip-audit -r requirements.txt
```
