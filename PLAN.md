# Farelin product plan

## Keep original web design and restore search-first Discover (2026-09-18)

Owner rejected the isolated app-inspired website concept. Remove its eight
tracked prototype/screenshot files; they remain recoverable in Git history.
Keep the native rollback/shared typography from a2def3a intact. The concept
never replaced production web pages, so reverting that whole commit would
incorrectly undo native typography rather than repair Discover.

Cause reproduced by failing layout contracts: the pre-existing signed-in
opportunity rail was rendered before the search composer, and its search link
pointed at /discover without an anchor. A full board pushed search below the
visible viewport. Move the composer ahead of the board and give it a named
trip-search anchor. Preserve all existing styling, search behavior and feed.

Verification: 153 web tests pass, including both formerly failing layout
contracts. API: 802 passed, two PostgreSQL-only tests skipped (20.75s). Local
browser: structured controls visible on entry; AI request and advanced options
open correctly without any AI/fare submissions. Production deployment and an
authenticated live search are not claimed. No iOS source or backend changes.
Production webpack build passes (27 pages); staged Gitleaks scan finds no leaks.
No push; owner deploys after review. Resume native retention roadmap next.

## Restore native design, share typography and preview reverse direction (2026-09-17)

User decision: undo e1c7f02's flattened web-to-native styling, retaining the
prior rounded cards, native navigation, controls, colors and globe materials.
Keep website typography in the app instead of reverting to SF approximations.
No business logic from the preceding Today/search stages is reverted.

- [x] Restore prior visual geometry/palette using a non-destructive inverse commit.
- [x] Bundle Bricolage Grotesque, Hanken Grotesk and JetBrains Mono with SIL OFL
  notices, explicit registered weights and Dynamic Type semantic scaling.
- [x] Build an isolated app-inspired website concept; never silently redesign
  production. Local fonts/geography, fictional demo fares, no provider/AI calls.
- [x] Verify native flows and packaging, web/API regressions, responsive concept.

Receipt: 100 native tests pass (89 unit, 11 UI), including all 15 font names,
font scaling, native Today title visibility and large-text price actions. Light
Today and dark accessibility screenshots inspected. Both Release simulator
schemes build. API: 802 passed, two PostgreSQL-only tests skipped. Web: 151 tests
pass and production webpack build succeeds (27 pages). Local prototype has no
horizontal overflow at 360/390/768/1024/1440px after fixing narrow nav and tablet
card-grid minimum widths. Demo search/bookmark feedback and trip sheet verified.
Dark/light screenshots were under design/previews/screenshots (prototype removed
at owner's request on 2026-09-18; recoverable from a2def3a). The prototype's
globe is a draggable Canvas projection, not the production native 3D renderer.
Physical-device typography QA remains manual. No migration, env change, push or
deployment. Staged Gitleaks scan passes with no leaks; Xcode window state is
excluded from the local commit.

Update 2026-09-18: owner chose the original website design; concept review is
closed. Resume the existing retention roadmap.

## Native retention — actionable Today (2026-09-17)

Handoff: search polish and hosted CI are green. Improve the existing Today
and watch navigation before adding more onboarding questions. Paid native
purchases, APNs setup and physical-device release QA remain external gates.

Decision: reuse dashboard observations and watch details for a clear next
action. Rejected: an extra opportunity feed fetch on Today (extra calls and
duplicated Discover), or streaks/engagement tracking (pressure and privacy cost).

- [x] A — derive truthful active/paused/expired states and useful ordering.
  Where: DashboardModels/tests. Verify fixed-date tests, end-day boundary,
  malformed dates and paused watches. Fence: no new fare requests or alerts;
  observed price is historical, never a current guaranteed fare.
- [x] B — put watch actions first, fold usage behind an accessible disclosure,
  and open the existing watch detail from Today. Where: DashboardView and
  authenticated tab routing. Verify empty/paused/active simulator flows,
  large text; inspect Reduce Motion guards and retain physical QA. Fence: keep backend ownership and session checks;
  do not automatically resume, preview, or run an AI search.
- [x] C — full native tests, both Release builds, API tests, web build and
  staged secret scan; update README and commit locally. Fence: do not push or
  describe simulator QA as physical-device/TestFlight proof.

Tripwires: a watch's end date has passed -> offer editing, not active-check
claims; dates are malformed -> show unavailable, not invented timestamps;
refresh fails with cached content -> keep content with a visible retry warning.
Next: deeper saved-intent/profile refinement and globe opportunity overlays.

Local receipt: 97 native tests pass (86 unit, 11 UI) on iPhone 17 Pro/iOS 26.5.
Simulator flows exercise watch -> details -> back, paused-watch review, and
large-text/dark-mode empty Today -> usage -> Discover. The final light-mode
screenshot was inspected, including readable teal status/observed-price text.
Both Production Release and Staging Release simulator builds pass. API:
802 passed, two PostgreSQL-only tests skipped in SQLite (20.28s). Web:
151 tests pass and the configured webpack production build compiles all routes.
A preliminary Turbopack invocation failed with a local Node architecture error;
the repository's configured webpack build passes, without web code changes.
No new migration, Railway variables, analytics, fare/AI calls or native payment
links. Hosted CI for this stage is not claimed; it will run after the owner pushes.
Staged Gitleaks scan passes with no leaks. Local commit headline: Improve native
Today watch actions and truthful monitoring states. No push in this stage.
Reduce Motion guards are implemented; actual accessibility-setting, signing,
APNs and physical-device release checks remain on the release checklist.

## Native CI visibility-loop investigation (2026-09-17)

Run 35146124574: 82 tests passed; long-results UI regression exceeded its
two-minute execution allowance. Saved screenshots show the results header, not
a blank viewport. Activity timing attributes about 47 seconds to three
redundant visibility checks after the Edit search control was already visible;
the spindump shows accessibility snapshot work. Replace Swift `for ... where`
scroll filters with early-exit loops, including sibling UI tests. Keep all
three repeated search/edit cycles, screenshots, assertions and scroll bounds.
Verify the 83-test suite locally and inspect the new hosted run before claiming
the CI failure is resolved. Preserve the user's Xcode window-state file.

Local receipt: all 83 tests pass on iPhone 17 Pro/iOS 26.5 with early-exit
loops, no assertion removal and no further timeout increase. Hosted run
35204175080 also passes all 83 tests on iOS 26.4.1; the long-results regression
finishes all three cycles in 58.5 seconds (previously exceeded 120 seconds).
Production UI/auth/provider code is unchanged in this fix. Both local Release
builds and both hosted Release build steps pass. All five jobs in hosted run
35204175080 are green; the iPhone job is confirmed resolved for commit bd4671a.

## Progressive native Explore revision (2026-09-16)

Handoff: user reported blank advanced-search viewport, cramped price CTA and
overwhelming controls. Preserve server-owned preferences, origin limits and AI
metering. Keep the user's Xcode window-state file untouched.

Decision: progressive sections within the existing composer, not separate
full-screen steps. Budget uses snapped checkpoints plus an explicit Flexible
choice; duration uses a normal slider. Retain a one-tap profile-default path.
Rejected: automatic search after each slider move (costs/changed intent), and
a rigid wizard that prevents revisiting earlier choices. A combined provider
link is a new search, not an observed protected ticket or guaranteed total.

- [x] A — investigate long-result scroll/layout bugs with isolated tabbed UI
  fixtures. Where: Discover and UI tests. Verify repeat search/edit in dark mode,
  compact and large text. Fence: no real account/provider charges for reproduction.
- [x] B — progressive When/budget/duration/mood/shape controls and concise
  refinement. Where: Discover/draft models. Verify reveal, sliders, defaults,
  edit preservation, explicit flexible budget and max-one-stop server filtering.
  Fence: no silent profile override or client-only comfort enforcement.
- [x] C — one combined provider action with exact flight routes/dates, omitting
  ground legs. Where: affiliate builder, itinerary builder and native cards/detail.
  Verify official provider prefill and route/date tests, no wrapped CTA.
  Fence: retain separate-ticket/ground warnings; do not claim a single fare quote.
- [x] D — verify, document and return to roadmap. Native tests + both Release
  builds, backend suite, secret scan. External signing/APNs gates stay explicit.

Tripwires: blank viewport not reproduced -> report that boundary honestly and
test lifecycle changes without claiming original proof; provider prefill differs
-> inspect provider-generated URL rather than invent parameters; no known stops
-> exclude unknown offers from a hard stop-count rule.

Verification: 83 native simulator tests (eight UI tests), 802 backend tests and
151 web tests pass. Two PostgreSQL-only tests are skipped in the local SQLite
suite. Production Release and Staging Release simulator builds pass. Repeat
search/edit cycles start on results; budget checkpoints, Flexible, a 30-night
slider selection, equal-size prompts and accessibility-size price buttons are
verified. The cramped CTA was reproduced; the original persistent blank screen
was NOT reproduced before changes. Separate scroll lifetimes replace the old
animated anchor handoff, but the reported physical-device glitch still needs
owner confirmation. Provider-generated Aviasales prefill confirms CPH → ATH →
SKP / SOF → CPH and all three DDMM dates; closing home must remain on a disjoint
route. No real fare search, account credentials or AI calls were used for fixtures.
Stop caps survive watch creation/preview/update via existing search_criteria JSON;
no database migration or new Railway variables. Release signing/APNs/inbox gates
remain in NATIVE-RELEASE.md; no automatic App Store submission or extra tracking.

## Native usability pass — search to next action (2026-09-16)

Handoff: release-foundation CI run 35099842363 and all four deployment statuses
for e2c773b succeeded. Apple credentials, signing and physical-device QA remain
owner gates. User approved continuing usability development; simulator work can
proceed without claiming those release gates are complete.

Decision: improve the existing Discover flow, not its search engine. Rejected:
a navigation rewrite (regression risk) and automatic relaxed/AI retries (hidden
costs and changed intent). No engagement tracking or forced notifications.

- [x] A — focus completed results and collapse the composer; Edit search restores
  the same draft. Where: DiscoverView. Verify native build/tests and simulator
  search -> results -> edit. Fence: never resubmit on scroll or edit.
- [x] B — actionable empty states with an explicit wider-date draft for Explore.
  Where: TripSearchStore/DiscoverView/TripSearchTests. Verify widening preserves
  route, budget, duration and comfort; no backend call until Find trips. Fence:
  no fabricated fares, automatic AI usage, or invisible scope relaxation.

Tripwires: invalid parsed dates -> keep original draft and offer manual editing;
reduced motion -> no animated scroll; failing native CI -> correct before release.

Verification: 77 native tests passed, including four isolated UI tests. Search
results are visible without returning through the composer, Edit preserves the
selected budget, and wider-date preparation preserves all other draft fields.
Both production Release and Staging Release simulator builds passed. No backend
contracts changed and no provider/AI calls were used for the UI fixture.


## Native release essentials (2026-09-16)

Handoff: preserve the existing SwiftUI app and FastAPI services. The September
15/16 integrity work is committed in `ac230fc`; verify deployed contracts before
assuming staging matches local code. Payments remain disabled. User approved
account controls, session reliability, native login, watch management, APNs,
and TestFlight preparation before a separate retention-focused UX pass.

Decision: reuse existing auth/privacy/watch endpoints, add verified native
provider-token exchange and APNs behind explicit configuration. Rejected: a
second auth database, automatic marketing opt-in, web Stripe purchases in iOS,
and a UI rewrite. Micro-motion should acknowledge actions, not delay them.

- [x] A — coordinate refresh and implement native account controls.
  Where: AuthSession, APIClient, Account/Authentication. Verify concurrent refresh,
  failed-network persistence, export/deletion/reset tests and simulator flows.
  Fence: no IP-based identity, no secrets in preferences, no production deletion
  as a diagnostic. View/export data only for the authenticated account.
- [x] B — Apple/Google native login with server-side signature/audience/issuer
  validation and no unverified-email account linking. Verify forged/expired/wrong
  audience tokens and legal consent rejection. Fence: no client-authoritative ID.
- [x] C — watch edit/preview/history and APNs opt-in/delivery/deep-link handling.
  Verify owner isolation, revoked devices, disabled APNs, retries/deduplication,
  permission denial and complete watch criteria round trips. Fence: no silent
  notification permission or marketing enrollment; no arbitrary notification URL.
- [x] D — CI, Release simulator build, privacy manifest and release checklist.
  Signed archive remains an owner gate, not completed. Verify all suites,
  secret/dependency scans, staging/Release builds and signed archive when possible.
  Fence: do not submit/release automatically or claim physical/APNs QA from mocks.

Tripwires: missing Apple/Google/APNs credentials -> leave providers unavailable
with exact owner setup; missing signing/profile -> prepare archive instructions
without weakening signing; failing CI -> fix before deploying. Physical iPhone,
real email, APNs and external TestFlight acceptance remain explicit release gates.

Code verification: 798 backend tests passed; two separate PostgreSQL regressions
passed (skipped unless TEST_POSTGRES_URL is set in the normal SQLite suite).
70 native tests passed, including two isolated UI tests and a light-mode text
contrast regression; 151 web tests and the
web production build passed. Real PostgreSQL migrations apply through 33 and
rollback/re-upgrade 32/33 successfully. Watch/account deletion with generated
trips was reproduced failing on PostgreSQL, corrected and added to CI. Gitleaks
scanned 159 existing commits clean; dependency audits are clean after patching h2
to 4.4.1. Final staged scan/deployment evidence is in NATIVE-RELEASE.md.
Installed Apple profiles lack Sign in with Apple and Push Notifications; do not
weaken entitlements to produce an upload. External login/APNs/inbox delivery and
TestFlight are not certified by passing mocks. Retention redesign remains next,
after owner configuration and physical functional QA.

## Native Discover and My World redesign (2026-09-15)

Handoff: keep `TripSearchStore`, `OpportunityStore`, `MyWorldStore`, the
FastAPI contracts, and the bundled Natural Earth geometry. Discover currently
stacks four complete opportunity cards before a long all-at-once form; My
World presents a MapKit projection, not an actual 3D Earth. Redesign only the
SwiftUI presentation and the globe renderer. The user's Xcode window-state
file is unrelated and must remain untouched.

Decision: Discover uses a compact observed-fare preview and an essentials
composer, with trip shape/destinations in the main flow and precision controls
disclosed on demand. My
World uses a textured native sphere with geographic hit testing, while the
country browser remains the accessible fallback. Rejected: a full app rewrite,
an embedded web globe (gesture/state bridge), retaining the flat MapKit view,
or asking the provider to supply aesthetic globe data. Do not label cached
prices as live.

### Stage 1 — compact Discover

Visible result: users can scan a fare sighting and launch structured search
without scrolling through a wall of nested controls.

1. Goal: put a restrained observed-opportunity teaser below the heading and
   disclose the full board only when requested. Where: `DiscoverView`. Verify:
   board still uses real observed DTOs and opens the same trip details.
   Fence: no sample prices in the signed-in board.
2. Goal: show window, budget, duration, mood, trip shape and destination in
   the main flow; disclose origin overrides and precision inputs in an expandable
   section. Where: `DiscoverView`, existing `TripSearchStore`. Verify:
   structured submit reaches the existing endpoint; multi-city/open-jaw
   controls still work; no extra AI charge. Fence: search overrides remain
   higher priority than profile defaults.

### Stage 2 — tactile native Earth

Visible result: a true sphere with recognizable country outlines and personal
visited/lived/wishlist colors rotates by touch, zooms by pinch, and taps a
country to open its existing sheet.

1. Goal: transform bundled country polygons into a low-resolution, theme-aware
   equirectangular texture and a reusable geographic hit-test index. Where:
   My World globe implementation. Verify: known country coordinates map to
   the expected ISO-2 codes. Fence: no network map asset or fake country data.
2. Goal: render the textured sphere natively and wire touch/zoom/selection;
   preserve the country browser and state update route. Where: `MyWorldView`.
   Verify: simulator build/tests plus visual/gesture check on iPhone; reduced
   motion and low-power disable idle spin. Fence: no MapKit globe masquerading
   as 3D and no unbounded texture redraw per frame.

Risk tripwires: if texture orientation or tap mapping fails, stop and correct
the geographic transform before shipping; if first-frame texture generation
causes visible delay, prepare it once and cache it. SceneKit is a pragmatic
iOS 17-compatible renderer here, but its newer-platform deprecation means
renderer migration should remain possible without changing country-state
services. The browser covers tiny countries and accessibility.

2026-09-15 code status: Stage 1 and Stage 2 presentation changes are in the
SwiftUI app. The simulator build and geographic tests passed; the rendered
texture and country gestures still require physical-iPhone visual QA before
an App Store build. Do not infer visual correctness from a passing unit test.

## Current cross-platform redesign workstream (2026-09)

Handoff: Farelin already has Next.js, FastAPI, a scheduled cached-fare board,
structured/AI search, trip details, watches, a travel map, and a SwiftUI iPhone
client. Keep those contracts. The new product hierarchy is structured,
budget-first discovery → trip inspection → external price check; Earth is a
secondary path and Ask Farelin is a contextual shortcut. Stage A is next:
show origin-specific, observed opportunities before either app asks for a
prompt. Continue with Stage B fast controls, then details/Earth and supporting
flows. Preserve the user's Xcode window-state file; it is not source code.

Decision: extend the existing cached database and trip builder into a
read-only personalized feed, then reuse the existing search route for quick
controls. Rejected: querying Travelpayouts on every home view (cost/rate
limits), hardcoded inspirational fares (dishonest), or replacing FastAPI and
SwiftUI with a new stack (high regression risk). The public board remains
explicitly labelled sample origins; the signed-in feed uses only profile
airports. A cold cache is an honest empty state, not a fabricated deal.

### Stage A — opportunity first (implemented and simulator-verified)

Visible result: web and iPhone show observed opportunities from a user's own
airports on opening, without spending an AI search or calling the provider.

1. Goal: expose bounded origin-specific cached round trips with individual
   price-observation times. Where: cached deals repository, a protected
   `GET /me/opportunities`, backend tests. Verify: seeded Postgres test returns
   only the owner's origins; no provider call; empty/stale responses are labelled;
   `pytest -q`. Fence: no fake live label, per-request provider search, or public
   caching of personalized data.
2. Goal: put the feed above search in web Discover/home and native Discover.
   Where: Next.js Discover/home, SwiftUI Discover, shared opportunity DTOs.
   Verify: real seeded fares open their trip or provider link; signed-out web
   still labels Central European examples; `npm test`, `npm run build`,
   `xcodebuild test`. Fence: no default to someone else's airports and no
   synthetic flight times presented as actual times.

### Stage B — fast structured discovery (implemented initial quick controls)

Visible result: a user can choose origins, a date window, flight budget,
length and travel mood, then see trips without using AI quota.

1. Goal: make structured controls primary; keep advanced route shapes behind
   progressive disclosure. Where: web Discover, native Discover, URL/state
   helpers. Verify: one tap on a budget/date chip updates visible constraints;
   search reaches `/trips/search` or `/trips/advanced-search`, not `/ai/search`;
   back navigation retains results. Fence: do not infer actual weather from a
   destination-style tag.
2. Goal: move Ask Farelin to a secondary action that reveals editable parsed
   constraints and then the same trip cards. Where: web/native Discover UI.
   Verify: AI search still works once; editing an interpretation re-runs a
   structured search without another AI charge. Fence: no chatbot home screen
   or invented prices.

### Stage C — destination inspection and Earth (date-only bundles and country inspection implemented; visual overlay pending)

Visible result: a fare card and a selected country both lead to inspectable,
provider-checkable trips with the same freshness language.

1. Goal: raise price/date/airport hierarchy in cards and details; show only
   evidence-backed alternative airports/dates. Where: web/native trip rows and
   detail. Verify: cached bundle shows date-only where times are unknown;
   alternatives link to real returned fares. Fence: no invented usual-price or
   weather figures.
2. Goal: attach country opportunity counts/prices to Earth selections; reuse
   MapKit/Three geometry and travel-map state. Where: feed-derived geography
   adapter, web World, native My World. Verify: tapping a country reaches the
   fare list for that country; unavailable countries say insufficient data.
   Fence: the globe remains optional, not the only search control.

### Stage D — saved intent, progressive profile, voice and polish

Visible result: a trip/search can become a truthful saved watch; onboarding
reaches the feed sooner; optional speech fills search controls without turning
into a conversation.

1. Goal: align saved-watch scope with supported schema; shorten initial profile
questions and offer later preference prompts. Where: web/native onboarding,
watches. Verify: a watch created on one client appears on the other; unsupported
ordered multi-city watch is refused clearly. Fence: no destructive migration
or silent country/region-to-anywhere watch conversion.
2. Goal: research and implement on-device speech permission/privacy flow only
where platform APIs and App Store disclosures are verified. Where: native voice
action, privacy copy. Verify: permission denial, dictation, and edit-before-
search paths; no audio sent to arbitrary services. Fence: voice optional and
no automatic metered search on a partial transcript.
3. Goal: finish responsive, Dynamic Type, VoiceOver, Reduce Motion, keyboard,
loading/empty/error states. Where: shared design tokens and screen tests.
   Verify: 360/390/768/1024/1440px web checks and iOS simulator/a11y checks.
   Fence: no blanket cards/gradients or dead controls.

Risks and tripwires: if profile origins have no cached rows, show a clear cold
cache state and the sample board separately rather than borrowing its prices;
if a provider fare lacks flight times, cards show dates only; if MapKit/Three
costs frame time on a real phone, reduce geometry/rotation before adding more
effects. Revisit this plan at each visible stage boundary and record changes.

2026-09-15 progress: private `GET /me/opportunities` is a capped Postgres
read of dated cached returns from profile airports only, with provider sighting
times distinct from refresh stamps. Home and Discover on web and native
Discover show that personal board before asking for a search. Structured
date/budget/length/mood controls are primary; AI remains explicit and
secondary. Bundle cards suppress internally synthesized clock times, leg
prices, stops and baggage claims, and scoring skips unsupported clock/bag/
stop components. Itinerary generation also ignores placeholder clock times
and reserves date-only bundle travel days. Backend/web suites passed (752
Python, 151 web); 44 iPhone
simulator tests passed on iOS 26.1. Country sheets/panels now show real
board fares when available. Still to build: geometry-linked opportunity overlays,
evidence-backed alternative dates, photo/media research, optional voice,
and deeper watch/onboarding refinements. Cold-cache states stay honest.
Local browser checks on web home and Discover at 360, 390, 768, 1024 and
1440px showed viewport width equals document width (no horizontal overflow);
the 390px landing/search first folds were visually reviewed. Provider-backed
and signed-in production UI still need manual staging QA.

## Handoff block

Farelin is a production Next.js + FastAPI travel application that discovers
observed flight-price opportunities, builds complete trip ideas, saves watches,
sends email alerts, and stores a personal travel map. The next product is a
native, iPhone-only SwiftUI app. It reuses the existing FastAPI/PostgreSQL
backend as the sole authority for users, profiles, searches, provider data,
scoring, watches, AI, entitlements, and travel history. It is not a WebView
port and must not duplicate fare or entitlement logic on-device.

Build with Xcode 26.6, the iOS 26 SDK, and Swift 6 strict concurrency. The
interface adopts Farelin's visual identity through native navigation, tabs,
sheets, search, haptics, accessibility, and an interactive native Earth.
Minimum deployment is iOS 17 to avoid excluding otherwise compatible users;
iOS 26-only presentation APIs are availability-gated. The first public app is
iPhone-only and requires sign-in before search. iPad comes later.

Two explicit schemes prevent environment mistakes:

- `Farelin Staging` -> staging API/database, staging APNs, `.staging` bundle ID.
- `Farelin` -> production API/database, production APNs, App Store bundle ID.

There is no Stripe checkout, web-upgrade link, or StoreKit purchase UI in the
first app. A disabled `PurchaseProviding` seam is included so StoreKit 2 can be
implemented later. Backend entitlements remain authoritative.

## Decisions and rejected alternatives

### Native SwiftUI client — chosen

SwiftUI gives Farelin first-class navigation, sheets, accessibility, haptics,
Keychain, AuthenticationServices, APNs, MapKit, and App Store quality. The
existing backend means little business logic needs to be rewritten.

- Rejected React Native/Expo: faster cross-platform expansion, but adds a
  JavaScript/native bridge and makes Farelin's globe, auth, notifications, and
  iOS-specific finish harder to make excellent.
- Rejected full-app WebView: fastest, but duplicates the website experience,
  weakens native UX, and creates unnecessary App Review/minimum-value risk.
- Rejected separate mobile backend: doubles authorization and provider logic.
  Add narrowly scoped mobile auth and device endpoints to the existing API.

### Signed-in product — chosen

The app opens at authentication and requires an account before fare or AI
search. This controls model/provider cost and gives Farelin a durable channel
for watches, email, and push. The public website remains the product preview.
The backend enforces this; the app does not merely hide anonymous controls.

### Native MapKit globe — superseded by tactile Earth redesign

The initial native implementation used MapKit overlays. The 2026-09-15
redesign replaces that surface with a native textured sphere using the same
local Natural Earth geometry and existing travel-map state API. Keep a
searchable country list as the accessible and low-precision fallback.

- Rejected embedding the existing Three.js globe: code reuse is attractive,
  but a WKWebView bridge would complicate gestures, themes, accessibility, and
  state synchronization in a flagship native feature.
- Rejected a custom Metal renderer initially: maximum control, excessive cost.

### Mobile bearer sessions — chosen

Web sessions remain httpOnly cookies. Native sessions use short-lived bearer
access tokens and rotated refresh tokens stored only in Keychain. Existing
resource ownership and entitlement dependencies accept either authenticated
session type. Cookie requests keep CSRF protection; bearer requests do not
depend on cookies and must reject tokens in query strings.

## App structure

```text
apps/ios/
  Farelin.xcodeproj
  Config/                 xcconfig files; no secrets
  Farelin/
    App/                  app entry, environment, root/auth routing
    Core/
      API/                typed client, transport, DTOs, errors
      Auth/               Keychain session and refresh coordination
      DesignSystem/       colors, typography, buttons, cards, states
      Notifications/      permission and device registration
      Persistence/        non-secret local cache
    Features/
      Authentication/
      Onboarding/
      Dashboard/
      Discover/
      TripDetail/
      Watches/
      MyWorld/
      Account/
      Billing/            entitlement display + disabled StoreKit seam
    Resources/            assets, localized strings, country geometry
  FarelinTests/
  FarelinUITests/
```

Use small feature stores built with Swift's Observation framework and protocols
at network/Keychain/APNs boundaries. Do not introduce a large state-management
framework. UI never infers plan access, fare confidence, or trip scores.

## Stage 1 — walking skeleton and environments

Visible result: both app schemes launch in an iPhone simulator with Farelin's
native theme, show API health, and cannot accidentally use the wrong backend.

1. Goal: create the SwiftUI iPhone app, test targets, asset catalog, and schemes.
   - Where: `apps/ios/Farelin.xcodeproj`, app entry, test targets.
   - Verify: `xcodebuild build` succeeds for Staging and production schemes.
   - Fence: no screen-by-screen port and no iPad target.
2. Goal: create typed, non-secret environment configuration.
   - Where: checked-in base/staging/release `.xcconfig` files; Info.plist keys.
   - Verify: Staging displays the staging host; Release displays production;
     a test fails if either uses localhost or the other's host.
   - Fence: API keys, APNs keys, OAuth secrets, and Stripe secrets never enter
     the app bundle or repository.
3. Goal: establish the native Farelin design system and reusable states.
   - Where: semantic color assets, typography, spacing, buttons, badges,
     loading/empty/error/offline views.
   - Verify: a component gallery renders in light/dark, Dynamic Type XXL,
     reduced motion, and VoiceOver-labelled controls.
   - Fence: adapt Farelin's identity; do not pixel-copy web navigation.
4. Goal: add API transport and `/health` connectivity.
   - Where: actor-based `APIClient`, Codable envelope/error types.
   - Verify: simulator shows connected/degraded without exposing raw errors.
   - Fence: no provider secrets or direct provider/AI API calls from iOS.

## Stage 2 — secure native authentication

Visible result: a real account can sign in, close/reopen the app, refresh its
session, and sign out; a second user cannot access the first user's resources.

1. Goal: add mobile login, refresh, logout, and one-time OAuth exchange APIs.
   - Where: existing FastAPI auth service/routes/schemas and refresh sessions.
   - Verify: access expiry refreshes once atomically; replaying a rotated token
     revokes the session family; web cookie tests remain green.
   - Fence: never return tokens from existing browser endpoints or URLs.
2. Goal: add native email/password sign-in and account creation.
   - Where: Authentication feature and Keychain session store.
   - Verify: tokens exist in Keychain, never UserDefaults/logs; relaunch stays
     signed in; logout revokes server session and clears Keychain.
   - Fence: no anonymous search and no local plan flags.
3. Goal: implement Sign in with Apple.
   - Where: AuthenticationServices client + backend identity verification.
   - Verify: nonce, issuer, audience, signature, and replay checks; private relay
     email works; account linking requires authenticated confirmation.
   - Fence: trust no name/email field without validating Apple's identity token.
4. Goal: implement Google login through a one-time backend exchange.
   - Where: Google iOS OAuth client, backend OAuth exchange, universal link.
   - Verify: canceled, invalid-state, duplicate-email, and successful flows.
   - Fence: no client secret in iOS and no bearer token in redirect URLs.
5. Goal: enforce mobile authentication server-side on costly operations.
   - Where: mobile API policy/dependencies for AI, fare search, watches.
   - Verify: anonymous mobile requests receive 401 before provider/model calls.
   - Fence: do not remove the website's intentionally public preview behavior.

## Stage 3 — native shell, onboarding, profile, and dashboard

Visible result: a signed-in user completes onboarding, relaunches, and sees a
native dashboard populated from the same account as the website.

1. Goal: build root navigation: Dashboard, Discover, Watches, My World, Account.
   - Where: native TabView + NavigationStack routes and deep-link router.
   - Verify: state restoration and back gestures work; tabs preserve position.
   - Fence: no web navbar/sidebar metaphors.
2. Goal: port the full profile flow using existing location/airport APIs.
   - Where: onboarding sheets, location autocomplete, airport recommendations,
     travel styles, budget, spontaneity, comfort rules, notifications.
   - Verify: Copenhagen and other real locations resolve; airport plan limits
     are enforced by API and explained before Continue.
   - Fence: no hardcoded airport menu and no duplicated recommendation math.
3. Goal: build dashboard and usage/entitlement display.
   - Where: dashboard summaries, profile completion, recent alerts, watches.
   - Verify: Free/Trial/Pro values match `/billing/status`; offline uses clearly
     labelled last-loaded data.
   - Fence: no upgrade or Stripe CTA in the first binary.

## Stage 4 — search, results, and trip planning

Visible result: the signed-in user runs AI or advanced search and opens a full
trip recommendation with honest fare metadata and a generated itinerary.

1. Goal: build AI search with parsed-filter review and staged loading feedback.
   - Where: Discover feature using existing AI search endpoint.
   - Verify: quota errors, provider errors, over-budget results, and edits all
     render deliberately; one search consumes one server-side allowance.
   - Fence: the app never calls OpenAI or an MCP server directly.
2. Goal: build advanced search with profile-default source labels.
   - Where: native forms/sheets using preference-resolution response fields.
   - Verify: explicit dates/origins/styles/comfort override the profile.
   - Fence: do not reimplement PreferenceResolutionService in Swift.
3. Goal: build native trip cards and detail.
   - Where: results list, trip detail, provider link handoff.
   - Verify: return/open-jaw/multi-city routes, warnings, observed time,
     confidence, deal/fit scores, baggage, and over-budget state render.
   - Fence: only “Check price/View deal/Open flight search”; never guarantee.
4. Goal: expose itinerary generation and caching.
   - Where: Trip Detail itinerary sections and cost disclosures.
   - Verify: arrival/departure constraints appear; cached reopen uses no AI call.
   - Fence: no invented flight facts or exact-cost claim without a source.

## Stage 5 — watches, email continuity, and native push

Visible result: a user saves a watch, receives a deep-linked APNs alert, opens
the matching trip, and can pause/delete the watch on either web or iOS.

1. Goal: build native watch creation/list/edit/pause/delete.
   - Where: Watches feature against existing saved-watch endpoints.
   - Verify: plan limits and daily/weekly permissions match the backend.
   - Fence: no device-only watches; web and iOS must show the same records.
2. Goal: add privacy-aware device installation storage.
   - Where: new user-owned device table/migration, APNs registration endpoints,
     GDPR export/erasure, token rotation/deactivation.
   - Verify: cross-user access denied; account deletion removes installations;
     stale or invalid APNs tokens deactivate.
   - Fence: device tokens never appear in logs or analytics.
3. Goal: add APNs delivery to the existing notification worker.
   - Where: notification provider abstraction and scheduled alert flow.
   - Verify: sandbox TestFlight device receives one notification; cooldown and
     dedupe prevent duplicates; email preferences still behave independently.
   - Fence: do not claim delivery until APNs accepts the notification.
4. Goal: implement deep links and notification controls.
   - Where: app router, associated domains, notification settings.
   - Verify: foreground/background/terminated opens route correctly; denied
     permission leaves email alerts working.
   - Fence: ask permission contextually, after explaining the benefit.

## Stage 6 — My World and interactive globe

Visible result: the personalized native globe displays country status and route
origins; tapping a country opens a native sheet and edits sync with the web.

1. Goal: load canonical country geometry and catalogue without duplicating IDs.
   - Where: bundled simplified geometry + API country catalogue adapter.
   - Verify: numeric geometry ID maps to the same ISO code as the backend.
   - Fence: no display-name matching and no second country truth source.
2. Goal: build a native interactive Earth with route cues and selected origin airports.
   - Where: My World globe renderer, geometry, camera, theme adaptation.
   - Verify: smooth interaction on a supported physical iPhone; reduced motion
     stops auto-rotation; low-power mode reduces overlays.
   - Fence: visual fidelity must not block accessible country search/list use.
3. Goal: add visited/lived/wishlist and visit editing sheets.
   - Where: country inspector and existing travel-map endpoints.
   - Verify: edits appear after web refresh and vice versa; repeated and partial
     dates survive round-trip.
   - Fence: do not infer dates or expose private history publicly.
4. Goal: connect wishlist countries to Discover.
   - Where: native deep-link/search handoff.
   - Verify: explicit country reaches search and overrides profile defaults.
   - Fence: handoff starts discovery, not fake trip creation.

## Stage 7 — account, privacy, StoreKit seam, and resilience

Visible result: the complete signed-in product handles account security,
privacy rights, connectivity failures, and entitlement states natively.

1. Goal: build account/security/email verification/password flows.
   - Where: Account feature and existing auth endpoints.
   - Verify: verification deep links, password reset, logout-all if available,
     export, and deletion work on-device.
   - Fence: destructive actions require explicit confirmation.
2. Goal: add native privacy controls and data export sharing.
   - Where: Account/Privacy sheets and system share sheet.
   - Verify: export is downloaded only after authentication and stored in a
     temporary protected file removed after sharing.
   - Fence: no sensitive export in caches or logs.
3. Goal: scaffold future StoreKit 2 without purchase UI.
   - Where: `PurchaseProviding`, `DisabledPurchaseProvider`, transaction DTOs,
     backend receipt/transaction endpoint interfaces behind feature flags.
   - Verify: production app exposes no purchase path; a fake provider can drive
     entitlement-state unit tests.
   - Fence: no unfinished IAP product, external Stripe link, or fake Pro state.
4. Goal: add resilient cache/offline behavior.
   - Where: URLCache and small protected local snapshots.
   - Verify: last dashboard/map can be viewed offline with a timestamp; searches
     and writes explain that connectivity is required.
   - Fence: never cache auth secrets, raw provider payloads, or AI prompts.

## Stage 8 — TestFlight and App Store release

Visible result: external TestFlight users complete the whole product flow, then
the reviewed build is released with production services and truthful metadata.

1. Goal: complete automated verification.
   - Verify: Swift unit/UI tests, backend suite, web suite, both iOS schemes,
     API contract checks, secret scan, and clean archive all pass in CI.
   - Fence: do not weaken web/API gates to ship iOS.
2. Goal: complete physical-device QA.
   - Verify: small/large supported iPhones, light/dark, Dynamic Type, VoiceOver,
     reduced motion, low power, offline, poor network, notification states.
   - Fence: simulator success is not physical-device proof for globe/APNs.
3. Goal: run external TestFlight validation.
   - Verify: at least 20 invited target travelers; measure activation (profile +
     first search), watch creation, notification opt-in, and four-week return.
   - Fence: no incentivized reviews or fabricated engagement.
4. Goal: prepare App Store privacy, review, and support material.
   - Verify: privacy nutrition labels match actual SDK/data use; reviewer demo
     account works; account deletion is discoverable; support/privacy URLs live;
     age-rating questions complete; no purchase UI exists.
   - Fence: screenshots and metadata never promise live/cheapest/guaranteed fares.

## Owner-only setup, kept separate from coding

1. Create a staging Railway environment/project with its own EU PostgreSQL,
   app secret, OAuth credentials, Resend test sender, and no production users.
2. Register production and staging bundle IDs and enable Sign in with Apple,
   Push Notifications, and Associated Domains.
3. Create an APNs signing key and place it only in Railway secrets.
4. Create Google iOS OAuth clients for both bundle IDs; backend secrets stay on
   Railway and only approved public client IDs enter app configuration.
5. Create the App Store Connect app record, internal tester group, privacy
   answers, support URL, and reviewer account when Stage 8 begins.

## Risks and tripwires

- Auth split: if a mobile token bypasses an ownership check or changes browser
  cookie behavior, stop Stage 2. Keep one user resolver and run all web auth tests.
- Environment contamination: if a staging build can reach production, stop.
  Bundle IDs, schemes, icons, associated domains, APNs, and API hosts must differ.
- Globe performance: if interaction drops frames on the oldest supported test
  iPhone, simplify geometry/overlays before adding effects; keep the list fallback.
- App Review billing: if any screen promotes Stripe or unlocks digital features
  through an external purchase, remove it from the first binary. StoreKit comes
  as a reviewed later phase.
- Provider honesty: if API data is indicative, iOS must display indicative and
  observed time. A polished native card never upgrades confidence.
- Scope: “include everything” means feature parity at release, not building all
  screens simultaneously. Each stage remains independently testable.

## Status

- [x] Product, platform, environment, authentication, scope, and billing decisions
- [x] Stage 1 — local walking skeleton and environment-safe schemes
  - Both simulator schemes compile; native unit and UI tests pass.
  - Production is connected to `www.farelin.com`; the deliberately separate
    staging host remains unavailable until its owner-only Railway setup exists.
- [ ] Stage 2 — secure native authentication
  - Email/password signup, login, rotated relaunch, logout, Keychain storage,
    native verification codes, bearer authorization, and first-request access
    refresh are implemented and validated against the EU staging deployment on
    a physical iPhone.
  - Sign in with Apple and Google native exchange remain before this stage is
    complete; refresh coordination must be centralized as more feature stores
    begin issuing authenticated requests concurrently.
- [x] Stage 3 — shell, onboarding, profile, dashboard
  - Native iPhone tabs and a real `/me/dashboard`-backed Today screen are
    implemented. Usage, entitlements, saved-watch summaries, loading, empty,
    and retry states do not duplicate backend plan logic.
  - The complete native travel-profile flow uses the backend city directory,
    origin-safe airport recommendations, plan-aware origin limits, structured
    comfort preferences, and existing profile persistence. New accounts are
    gated into onboarding; completed profiles can be edited from Account.
  - Simulator unit/UI coverage is green. The full onboarding flow and deployed
    staging geo endpoints are validated on a physical iPhone.
- [ ] Stage 4 — search, results, trip planning
  - The first native Discover slice is implemented against authenticated
    `/ai/search`: profile origins, progressive loading, parsed-request context,
    provider caveats, empty/error states, and truthful observed/estimated fare
    cards all remain thin clients of backend search and entitlement logic.
  - Native suggestion detail and cached AI itinerary generation are implemented:
    flight legs, transfers, warnings, provider links, personalized day plans,
    estimated extra costs, and provider disclaimers remain tied to backend data.
    Rapid-tap guards prevent duplicate metered search and itinerary requests.
  - Advanced structured search is implemented with worldwide place autocomplete,
    ordered multi-city stops, dates, trip length, budget, travel style, comfort,
    transfer and origin overrides. The authenticated backend resolves omissions
    from the profile, returns source labels, and consumes no AI allowance.
  - Explore now accepts one selected or exactly typed world region, country, or
    continent for fare-backed multi-city/open-jaw proposals; explicit ordered
    stops still win. Unknown regions are rejected and broad provider-budget
    truncation is disclosed. UN M49 subregions are bundled, not fetched live.
  - Weekly watch creation and separate private saved-fare bookmarks are
    implemented; an observed multi-city fare can be saved without pretending
    the ordered route is a recurring watch.
  - Integrity pass: geographic destination intent is distinct from ordered stops;
    region searches may expose explicitly labeled return alternatives without an
    extra discovery request. Chain integrity is validated before persistence;
    all flight/ground segments display on native/web cards with per-flight links.
    Duration alternatives are bounded; dates no longer leak raw ISO timestamps.
  - Saved fares preserve normalized private itineraries after suggestion expiry.
    Watches preserve semantic regions/ordered stops through preview and scheduled
    search, using the canonical Discover origin directory instead of seed-only
    validation. Staging currently lacks the new Save Fare endpoint: deploy API
    migrations `20260915_0030` and `20260916_0031` before physical-device QA.
  - Verified September 16: 769 backend tests, 57 iOS simulator tests, and 151 web
    tests pass. Web production build and Release production iOS simulator build
    pass; Alembic has a single `20260916_0031` head; `git diff --check` is clean.
- [ ] Stage 5 — watches and native push
  - Existing watches and saved fare snapshots are visible in the Watches tab;
    semantic multi-city recurring watch criteria are implemented; native push
    and end-to-end real-email scheduled-delivery QA remain unfinished.
- [ ] Stage 6 — My World and interactive globe
  - Full alphabetized country browsing, search, country selection, state color,
    touch rotation/zoom, base pin, wishlist arcs, and a frameless SceneKit globe
    are implemented. Globe texture/wireframe/points now echo the web visual;
    exact web mesh parity and real-device frame/gesture QA remain open.
  - Removed timed step rotation in favor of a frame-synchronized display link;
    local sphere-coordinate picking and raw GeoJSON preserve polar rings, holes,
    and date-line seams. Automated geometry/rendering regressions pass; physical
    iPhone gesture/frame profiling remains required.
- [ ] Stage 7 — account, privacy, StoreKit seam, resilience
- [ ] Stage 8 — TestFlight and App Store release
