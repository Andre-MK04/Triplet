---
name: phase-wrap
description: "Wrap up a completed phase of work the way this project does it: verify to the depth the change demands, auto-commit when green with a phase-style message, bring README and roadmap memory up to date, and report with proof instead of claims. Trigger sentences: 'wrap up this phase', 'phase N is done', 'commit phase N and start phase N+1', 'finish this off properly', 'ship this phase'."
---

# The Phase Wrap-Up

## When it triggers
- A chunk of work (a phase, a feature batch, an integration) is functionally
  complete and needs to become a commit, updated docs, and a report.
- The user says a phase is done, or asks to move to the next one — wrapping
  the current one is implied.

## The one rule
**Nothing goes in the commit or the report unless it was actually run.**
Every claim must trace to a command executed in this session — a test count,
a build result, a response body, a screenshot. Anything not proven is not
"done"; it goes in the gaps list, stated plainly.

## The method

### 1. Verify — matched to what changed
Always, in this order:
- `cd apps/api && source .venv/bin/activate && python -m pytest -q` — suite
  must be green AND fast (~4s). A suddenly slow suite means a test is hitting
  a real API: stop and fix isolation before anything else.
- `cd apps/web && npm run build` — must compile with all routes.

Additionally, matched to the change:
- **UI changed** → walk the real flow in the browser preview (not just a
  screenshot of the landing page — click the actual feature).
- **Provider/integration changed** → one real end-to-end call (smoke test or
  live search) with the response inspected, never assumed.
- **Migration added** → run upgrade AND downgrade against a scratch DB.

### 2. Commit — automatically, once green
If and only if step 1 passed:
- `git status --short` first — confirm nothing secret-shaped is staged
  (`.env` must never appear; if it does, stop and fix `.gitignore`).
- One commit for the phase. Subject: `Phase N: <what it delivered>` (or a
  plain imperative headline for unnumbered work). Body: grouped bullets of
  what changed and why it's safe, ending with the real test count.
- Trailer: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Never push. Push and deploy are the user's call, always.

### 3. Update the paper trail
- README: fix exactly the sections this phase made stale (provider matrix,
  page lists, limitations, env vars) — no wholesale rewrites.
- Persistent memory: update the roadmap note (phase done, commit hash, what's
  next) so the next session starts oriented, not re-auditing.

### 4. Report
Lead with the outcome in one bold sentence. Then, all four, always:
- **Verification evidence** — real numbers: "162 tests, 3.7s", "15 routes",
  what was clicked, what the API returned.
- **Honest gaps** — what's still mock/demo, what was skipped, what's fragile.
  Demo or cached data is never described as live.
- **Blockers needing the user** — credentials, accounts, decisions; if there
  are none, say so.
- **Clickable file links** — `[file.py](path/to/file.py)` for the key changes.
End with the natural next step as a suggestion, not a question blocking work.

## The standards
- The test count in the commit message equals the count from the actual run.
- Zero uses of "should work", "likely", or "presumably" in the report —
  either it was run, or it's in the gaps list.
- A failing suite means NO commit: report the failure with output instead.
- Secrets never in a commit; `git status` checked before every `git add -A`.
- README diff touches only sections the phase touched.
- The report is readable by someone who stepped away mid-phase: no invented
  shorthand, no unexplained codenames.

## The output
A green verification run, one phase-style commit (hash cited), an updated
README + roadmap memory, and a report in the four-part format above —
delivered as one final message, not scattered across the turn.

## The honest limits
- This wraps *local* work. It cannot verify deployments, DNS, webhooks, or
  anything living in a provider dashboard — those claims stay out of reports.
- Auto-commit is for green states only. If the phase is half-working, the
  skill's job is to say so and stop — never to commit "progress" that fails.
- Pushing, deploying, deleting branches, or anything irreversible remains
  explicit-approval territory regardless of how green things are.
- A phase blocked on external input (API keys, account approvals) ends at an
  honest blocker report — not at a simulated completion.
- If verification itself is ambiguous (flaky test, intermittent failure),
  that's a bug-hunt, not a wrap-up: switch jobs rather than averaging over it.
