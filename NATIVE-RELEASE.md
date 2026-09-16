# Farelin iPhone release setup

The app reuses FastAPI auth/search/watch/privacy services. Minimum iOS 17,
iPhone only. Payments stay disabled; don't add a web Stripe purchase link to
the native app. This file is a release checklist, not a claim of App Store approval.

## Backend deployment

Run `python -m alembic upgrade head` on staging before testing a new native build.
Migration 32 adds short-lived Apple nonce challenges and encrypted OAuth refresh
tokens/client IDs for revocation. Migration 33 adds encrypted push devices and
bounded delivery outbox rows. Both are additive. API and hourly alerts worker
must use the same database and APP_SECRET. Never copy production user data into
staging. Apply migrations before the worker is updated.

The existing hourly `python -m app.scheduled.tick` warms fares, runs due email
watches and drains at most 100 push deliveries. Watch frequency/cooldown still
governs eligibility. Push supplements accepted email notifications; it is not an
independent real-time fare feed. Three attempts maximum, stale opportunities
discarded after one day, invalid APNs devices disabled. Delivery metadata is
pruned after 30 days, unused devices after 90 days. Device tokens/provider
refresh tokens are encrypted using an APP_SECRET-derived key; APP_SECRET
rotation therefore needs a re-encryption/reconnection plan, not a blind replacement.

## Apple sign-in

1. Enable Sign in with Apple on each actual App ID (`com.farelin.app.staging`
   and/or `com.farelin.app`). Check team/bundle settings in Xcode.
2. Create an Apple Sign in key for the correct primary App ID/group. Store its
   private `.p8` contents **only on Railway** as `APPLE_OAUTH_PRIVATE_KEY`.
3. Set `APPLE_OAUTH_TEAM_ID`, `APPLE_OAUTH_KEY_ID`, and
   `NATIVE_APPLE_CLIENT_IDS` to a comma-separated allowlist of native bundle IDs
   approved for that environment. The existing web service ID stays separate.
4. Check `/auth/native/providers` reports Apple available. On an iPhone, test
   new signup with terms consent, returning login, relay email and account deletion.

The backend verifies Apple's signature, issuer, audience, expiry and one-time
nonce, redeems the authorization code and encrypts the refresh token. Account
deletion revokes retained native Apple tokens before erasure. If Apple/billing
cancellation is unavailable, the account is preserved with a retryable error.
Users created via the older web Apple flow have no retained native refresh token;
review their Apple revocation path separately before expanding web Apple sign-in.

## Google sign-in

1. Create iOS OAuth clients for the exact bundle IDs in Google Cloud.
2. Use the official GoogleSignIn iOS SDK (pinned 9.2.0 plus resolved dependencies).
3. In ignored `apps/ios/Config/Staging.local.xcconfig` or
   `Production.local.xcconfig`, set the **public** identifiers:

   ```text
   GOOGLE_IOS_CLIENT_ID = your iOS OAuth client ID
   GOOGLE_SERVER_CLIENT_ID = your web/server OAuth client ID
   GOOGLE_REVERSED_CLIENT_ID = the reversed iOS client ID URL scheme
   ```

   No client secret belongs in iOS. Public identifiers may be supplied as Xcode
   build settings for CI/distribution instead of local files.
4. Railway `NATIVE_GOOGLE_CLIENT_IDS` must allow the ID token's audience (the
   server client ID when configured). Don't accept every client in a Google project.
5. Test new signup, cancellation, existing linked accounts and relaunch.

The backend verifies ID token signature/issuer/audience/expiry/sub/verified
email; it does not accept an email supplied separately by iOS. Automatic linking
to an existing password account is refused for non-Gmail/non-hosted-domain Google
addresses because Google may not remain authoritative for that external mailbox.
Google SDK sign-out follows the exchange; Farelin owns the ongoing session.

## APNs

Enable Push Notifications on the App IDs, then create an APNs token-signing key.
Set the following on the staging API **and** alerts worker:

```text
APNS_ENABLED = true
APNS_TEAM_ID = your Apple team ID
APNS_KEY_ID = your APNs key ID
APNS_PRIVATE_KEY = private .p8 contents, backend only
APNS_TOPIC = exact app bundle ID
APNS_ENVIRONMENT = sandbox
```

Development-signed builds use `sandbox` / the `development` entitlement.
TestFlight/App Store builds use APNs `production`, even when their API points
to staging. The staging scheme archives with **Staging Release**: staging API
and bundle ID, Release optimizations, no DEBUG UI-test code, production APNs.
Set Railway `APNS_ENVIRONMENT=production` for staging TestFlight; keep `APNS_TOPIC`
the staging bundle ID. The normal Release scheme targets production.

In Account, tap Enable push alerts. No OS permission prompt is shown before
this choice. Consent is stored locally per account, and disconnecting doesn't
automatically re-enable it on relaunch. Lock-screen content is generic; tapping
opens the watch through the authenticated API, not an arbitrary URL. Log out
disconnects the registered device best-effort; an offline disconnect may need
a retry. Active device ownership cannot be taken over by another account.
Account also lists active device identifiers and lets the owner disconnect old
devices. An active token cannot be reassigned by a different account; no tokens
are shown or returned in account exports. After the previous owner explicitly
disconnects, the same phone can reconnect under another account with a fresh
device identifier; old queued push deliveries are discarded, never reassigned.

## Watch management

Watches have detail, observation preview and check/email history screens.
Settings edits preserve geographic scope. The separate route editor searches
the real airport/place catalogue, supports explicit city order or broad regions,
and respects backend origin/frequency/watch limits. Changing the route clears
old ordered-stop/return-city constraints instead of retaining invisible filters.
Pause/resume stays distinct from permanent deletion. Deletion removes the watch,
outbox and history, but unlinks generated trips so bookmarks remain usable.

## Email validation (physical/inbox gate)

Do not send diagnostics to real users. With one staging test account you control:

- Sign up; receive and confirm the native six-digit code (10-minute TTL).
- Request a reset email; open the trusted web reset flow; sign in with new password.
- Create a weekly watch and a daily-entitled watch with available cached fares.
- Run the existing scheduler; inspect the watch's observation and delivery history.
- Confirm inbox arrival, not merely provider acceptance, and check unsubscribe.
- Verify `urgent_only` and `weekly_digest` preferences against actual scheduled
  eligibility; a weekly check is not a guarantee of a roundup email with no deals.
- Check the cron has the real Resend settings and `EMAIL_REQUIRE_REAL_PROVIDER=true`.

## Archive and TestFlight

```bash
/usr/bin/ruby apps/ios/scripts/sync_project.rb
xcodebuild -project apps/ios/Farelin.xcodeproj -scheme Farelin \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath /tmp/Farelin-release.xcarchive archive

# Staging TestFlight, with its own App ID/profile/backend:
xcodebuild -project apps/ios/Farelin.xcodeproj -scheme 'Farelin Staging' \
  -configuration 'Staging Release' -destination 'generic/platform=iOS' \
  -archivePath /tmp/Farelin-staging-release.xcarchive archive
```

Use Xcode Organizer to validate/distribute the signed archive. Do not treat an
unsigned archive or simulator build as upload-ready. No signing credentials are
committed or required for the CI simulator gate. Increase build/version numbers
before each upload. Resolve signing profiles/capabilities with your Apple account,
not by removing security entitlements. No automatic App Store submission.

Owner review: app name/icon/screenshots/support URL/privacy URL, truthful App
Store Connect privacy labels including Google SDK/privacy report, export
compliance questionnaire, review account with reachable inbox and observed
test fares, age rating and account-deletion instructions. A staging reviewer
account must not expose production accounts. Keep providers with missing access
unavailable and prices indicative, never guaranteed.

## Physical QA before release

- Email signup/verification, Apple/Google cancellation and relaunch persistence.
- Concurrent expired requests, offline relaunch retry and logout across tabs/screens.
- Structured/AI search; no double charge on repeated taps; over-budget labels.
- Return/open-jaw/multi-city chronology and per-leg provider links.
- Save/reopen/delete fare; edit/preview/pause/resume/delete watch, history.
- My World touch/pinch/country selection in light/dark/reduced-motion/Low Power.
- Dynamic Type, VoiceOver country browser, keyboard dismissal and small iPhone layout.
- Push denied/granted, foreground/background/cold-launch tap, logout then another
  account (no previous account content), APNs invalid-device handling.
- Account export contains only own data; deletion removes linked notification rows
  and revokes sessions; failure leaves account/billing access intact.

Retention-focused simulator UX work can proceed alongside owner configuration;
it does not replace the physical-device and signed-distribution release gates.

## Verification receipt — September 16, 2026

- Backend: 798 tests passed; two PostgreSQL-only tests skipped in the default
  SQLite run and passed separately against a migrated local PostgreSQL 16 database.
- Native: 70 tests passed, including two isolated UI tests on iPhone 17 Pro / iOS 26.1
  and a light-mode action-text contrast regression. Text actions use darker teal
  in light mode; mint-filled primary buttons keep their original identity.
- Web regression: 151 tests passed; Next.js production build passed.
- PostgreSQL: migrations through 33 apply; downgrade to 31 and re-upgrade passed.
  Reproduced and fixed linked-trip foreign-key failures for watch/account deletion;
  both paths now have a real PostgreSQL CI gate.
- Production Release and Staging Release simulator builds passed. The staging
  archive configuration preserves the staging API and strips DEBUG-only test code.
  **Signed archive is not upload-ready**: the
  installed profiles lack Push Notifications and Sign in with Apple. Enable the
  App ID capabilities and refresh provisioning in Xcode before archiving.
- Backend/runtime web dependency audits report no known vulnerabilities.
  h2 was updated to 4.4.1 after the audit found an advisory in 4.3.0.
- Gitleaks: 159 existing commits and the final staged changes scanned with
  redaction, no leaks found. No private keys/signing files are staged.

Scoped security review covered native provider verification, bearer-session
rotation, account erasure/export, watch ID ownership, APNs token/outbox boundaries,
safe notification destinations and client configuration. Disabled accounts cannot
return through OAuth; forged/expired/wrong-audience tokens and unverified emails
are rejected. Provider/device tokens are encrypted and excluded from responses,
exports and transport logs. There are no new payment/webhook/upload/LLM tools in
this phase. This is a code review plus regression checks, not a hosting audit or
penetration test, and it is not a guarantee that the app cannot be hacked.

Deployment receipt for `9aca6b5`: GitHub reports successful Vercel, staging API,
production API and alerts-worker deployments. Staging `/ready` reports ready;
native-provider status is available and push status rejects unauthenticated access.
Backend, frontend, dependency audit and secret/database CI jobs passed.

Follow-up receipt for `e2c773b`: CI run 35099842363 completed successfully,
including native simulator tests/builds, and all four deployment statuses are
successful. The subsequent Discover usability pass passed 77 native tests
(four isolated UI tests) and both Release simulator configurations locally.
Its DEBUG-only Discover fixture has no real account, fare provider or AI service
and is stripped from Release builds. Search-to-edit UI testing confirms visible
results and retained budget; date widening is an explicit draft, not a retry.

Still unverified externally: Apple/Google account configuration, real Resend
inbox delivery, APNs physical-device acceptance,
signed distribution and App Store Connect privacy/review metadata. Do not replace
these checks with mock results.
