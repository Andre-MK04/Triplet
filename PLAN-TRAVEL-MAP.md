# Triplet Travel Map — implementation plan

## Handoff block

Triplet is a Next.js 16 / React 19 web app backed by FastAPI, SQLAlchemy,
Alembic, and PostgreSQL. Authentication uses httpOnly cookie sessions and all
user-owned API routes resolve the authenticated `UserDB`. The existing
`RouteGlobe` is a React Three Fiber dotted globe with route arcs but no country
polygon geometry. Build Travel Map as an authenticated `/world` feature using
the existing design system and globe controls. Persist normalized country
relationships and individual visits, use one canonical ISO country catalog,
render a simplified Natural Earth polygon overlay keyed by stable IDs, and
extend GDPR export/erasure plus selective AI context. Do not replace auth,
database, the globe library, or the search workflow.

## Chosen approach

- **Normalized `user_countries` + `country_visits`.** `user_countries` stores
  durable visited/lived/wishlist facts; `country_visits` stores zero or more
  dated or undated visit/residence records. This keeps “visited with no date”
  valid and makes repeated visits queryable.
- **One canonical country catalog served by the API.** It contains ISO alpha-2,
  alpha-3, numeric geometry ID, display name, continent, and whether it counts
  toward Triplet’s configurable world total. The seven continents are also
  centralized.
- **Natural Earth overlay inside the existing R3F globe.** Use low-detail
  TopoJSON and spherical polygon geometry, preserving Triplet’s core, route
  arcs, controls, theme, and reduced-motion behavior.
- **Dedicated `/world` page.** Desktop uses a compact side inspector; mobile
  uses a bottom sheet. A searchable list remains the accessible fallback and
  supports bulk additions.

Rejected alternatives:

- Store everything as JSON on `user_travel_profiles`: fastest initially, but
  weak for multiple visits, edits, ownership queries, GDPR, and future trip
  links.
- Build a separate 2D map: simpler picking, but conflicts with the product goal
  of turning Triplet’s existing globe into the personal map.
- Replace the globe with another globe framework: unnecessary visual and
  performance risk; a polygon overlay is enough.

## Stage 1 — secure travel-history API

Visible endpoint: an authenticated user can mark Iceland visited, refresh, and
receive Iceland from `GET /me/travel-map`.

1. Goal: add canonical country metadata and centralized totals.
   - Where: `apps/api/app/data/country_catalog.json`, loader/service, public
     country catalog route, catalog update script.
   - Verify: tests assert 195 counted countries, seven continents, stable ISO
     lookups, and alias-independent numeric geometry matching.
   - Fence: do not create a second frontend-maintained country-name list.
2. Goal: persist country facts and repeated visits.
   - Where: SQLAlchemy models and one Alembic migration for `user_countries`
     and `country_visits`.
   - Verify: `alembic upgrade head`; model tests cover repeated and partial-date
     visits.
   - Fence: no public/shareable map fields and no exact-date requirement.
3. Goal: expose protected read/write APIs with validation and ownership.
   - Where: travel-map schemas, service, router, audit events.
   - Verify: API tests for status transitions, bulk add, visit CRUD, duplicate
     handling, unknown ISO codes, and cross-user access denial.
   - Fence: no endpoint accepts a user ID from the client.
4. Goal: include travel history in GDPR rights.
   - Where: privacy export, erasure, retention tests.
   - Verify: export contains the owner’s country facts/visits and erasure leaves
     no linked rows.
   - Fence: never export auth secrets or another user’s data.

## Stage 2 — personal globe and country interactions

Visible endpoint: `/world` colors visited/lived/wishlist countries and selecting
a country opens real persisted details.

1. Goal: add a memoized, ISO-keyed polygon layer to the existing globe.
   - Where: `RouteGlobe`, country geometry asset/loader, small geometry helper.
   - Verify: hover/click reports the correct ISO code; theme and reduced-motion
     modes render; build output stays within a practical bundle increase.
   - Fence: preserve the current globe core, routes, controls, and homepage API.
2. Goal: build the responsive Travel Map view.
   - Where: `/world`, map stats, legend, country inspector, visit editor.
   - Verify: desktop hover/click and mobile tap/bottom-sheet flows; refresh
     preserves changes.
   - Fence: do not make color the only status signal.
3. Goal: add searchable bulk country entry.
   - Where: accessible country search/list modal.
   - Verify: keyboard search can mark several countries without dates; failures
     roll optimistic state back with an error.
   - Fence: do not require globe precision or travel dates.
4. Goal: integrate navigation without clutter.
   - Where: authenticated AppShell navigation/account links.
   - Verify: logged-in users can reach My World on desktop/mobile; logged-out
     access shows a proper sign-in state.

## Stage 3 — visits, discovery, and AI context

Visible endpoint: users can add/edit/delete multiple month/year visits and plan
a wishlist trip through Triplet discovery.

1. Goal: complete visit/residence editing with partial dates.
   - Where: visit editor and API schemas/service.
   - Verify: exact, month, year, and unknown precision round-trip; multiple
     visits display chronologically; deleting one does not erase other facts.
   - Fence: do not invent dates from incomplete input.
2. Goal: connect wishlist countries to search.
   - Where: country inspector and `/discover` destination hand-off.
   - Verify: “Plan a trip” opens Discover with the country explicitly present
     in the query and existing search behavior intact.
   - Fence: no booking flow and no fake fares.
3. Goal: expose compact travel-map context to recommendation logic.
   - Where: travel-map context helper and AI orchestrator prompt assembly.
   - Verify: relevant requests include visited/lived/wishlist ISO sets; normal
     requests do not include visit notes or a large history dump.
   - Fence: tool allowlists and backend validation remain unchanged.

## Stage 4 — verification and phase wrap

Visible endpoint: the complete flow is green locally and documented.

1. Goal: prove backend behavior.
   - Verify: `cd apps/api && .venv/bin/pytest -q` and
     `.venv/bin/alembic upgrade head` against a disposable database.
   - Fence: do not weaken existing tests to make new behavior pass.
2. Goal: prove frontend behavior and visual resilience.
   - Verify: `cd apps/web && npm run build`; manual checks at 390, 768, 1024,
     and 1440 px in dark/light themes and reduced-motion mode.
   - Fence: no unrelated redesign.
3. Goal: update project memory and ship a coherent commit.
   - Where: README feature/schema/run notes and this plan’s status.
   - Verify: clean diff contains no secrets or generated local databases.

## Risks and tripwires

- **Geometry bundle/performance:** tripwire is a noticeable globe frame-rate
  drop or a large first-load chunk. Fallback: 110m geometry, lazy-load only on
  `/world`, fewer polygon segments/mobile labels, accessible list always works.
- **Country-ID mismatch:** tripwire is any polygon selected by display-name
  matching. Stop and fix numeric-ID → ISO mapping in the canonical catalog.
- **Incomplete world geometry:** low-detail Natural Earth omits or makes tiny
  states hard to pick. Keep all 195 countries in the searchable interface and
  clearly treat the globe as a visual input, not the only input.
- **Status drift:** tripwire is UI code independently inferring transitions.
  Keep lived-implies-visited and display precedence in one backend service and
  return the derived primary status.

## Status

- [x] Stage 1 — secure travel-history API
- [x] Stage 2 — personal globe and country interactions
- [x] Stage 3 — visits, discovery, and AI context
- [x] Stage 4 — verification and phase wrap
