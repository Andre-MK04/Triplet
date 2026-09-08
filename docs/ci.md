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

**Dependency audit** — `pip-audit` is blocking. Runtime npm dependencies at high
or critical severity are blocking; the full development tree is reported as an
advisory because build tooling does not ship to users. The September readiness
pass upgraded Vitest and its Vite tree; both the runtime and full npm audits are
currently clean. Every new result still needs triage.

**Secret and database scan** — Gitleaks scans full repository history, and
focused checks reject tracked `.db`/`.sqlite` files and non-example `.env`
files. `apps/api/triplet.db` was tracked in a public repository until September
2026; the focused rule stops it coming back while Gitleaks catches credentials
embedded in ordinary source or history. All external CI actions are pinned to
immutable commit SHAs with their release line documented in comments.

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
