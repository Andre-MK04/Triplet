# Farelin Native iOS Plan

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
sheets, search, haptics, accessibility, and an interactive MapKit globe.
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

### Native MapKit globe — chosen

Use MapKit's globe camera, route overlays, and local Natural Earth country
geometry. Country state still comes from the existing travel-map API. Keep a
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
2. Goal: build MapKit globe with route arcs and selected origin airports.
   - Where: My World Map view, overlays, camera, theme adaptation.
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
- [ ] Stage 3 — shell, onboarding, profile, dashboard
  - Native iPhone tabs and a real `/me/dashboard`-backed Today screen are
    implemented. Usage, entitlements, saved-watch summaries, loading, empty,
    and retry states do not duplicate backend plan logic.
  - The complete native travel-profile flow uses the backend city directory,
    origin-safe airport recommendations, plan-aware origin limits, structured
    comfort preferences, and existing profile persistence. New accounts are
    gated into onboarding; completed profiles can be edited from Account.
  - Simulator unit/UI coverage is green. The onboarding flow still needs its
    final physical-device pass against the deployed staging geo endpoints.
- [ ] Stage 4 — search, results, trip planning
- [ ] Stage 5 — watches and native push
- [ ] Stage 6 — My World and interactive globe
- [ ] Stage 7 — account, privacy, StoreKit seam, resilience
- [ ] Stage 8 — TestFlight and App Store release
