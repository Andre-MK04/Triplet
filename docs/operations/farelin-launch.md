# Farelin production identity checklist

Farelin was formerly named Triplet. Public identity is Farelin; the repository,
historical migrations, persisted IDs, and `TRIPLET_*` limit variables retain
their old names for compatibility.

## Vercel

Set:

```text
NEXT_PUBLIC_SITE_URL=https://farelin.com
NEXT_PUBLIC_API_BASE_URL=/backend
API_PROXY_TARGET=https://<Farelin API Railway hostname>
```

Add `farelin.com` and `www.farelin.com` to the Vercel project. Make
`farelin.com` primary and configure `www.farelin.com` to redirect to it in
Vercel. Apex/`www` canonicalization must have a single owner, so the application
does not redirect between those hosts. The application redirects only the exact
old host `triplet-web.vercel.app`; preview `*.vercel.app` deployments are not
redirected. Verify path and query preservation after deployment.

Do not configure `farelin.com` to redirect to `www.farelin.com` while also
configuring `www.farelin.com` to redirect back to the apex. That creates an
infinite redirect loop that browsers commonly report as being unable to open
the page.

## Railway API

Set the production values documented in `apps/api/.env.production.example`, in
particular:

```text
APP_NAME=Farelin
FRONTEND_URL=https://farelin.com
AUTH_PUBLIC_BASE_URL=https://farelin.com/backend
ALERTS_PUBLIC_BASE_URL=https://farelin.com
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=
ENABLE_DEV_TOOL_ENDPOINTS=false
EXPOSE_API_DOCS=false
RATE_LIMIT_REQUIRE_SHARED=true
ADDITIONAL_ALLOWED_ORIGINS=
```

Keep `AUTH_COOKIE_DOMAIN` unset. The OAuth callback goes through Farelin's
same-origin Vercel proxy, so host-only cookies are both sufficient and safer.
If a preview must exercise authenticated write flows, add that one exact HTTPS
preview origin temporarily to `ADDITIONAL_ALLOWED_ORIGINS`; wildcards are not
accepted. Public preview pages continue to work without being redirected.

## Google OAuth

In Google Cloud Console update the consent-screen application name and links:

- Application name: `Farelin`
- Homepage: `https://farelin.com`
- Privacy: `https://farelin.com/privacy`
- Terms: `https://farelin.com/terms`
- Authorized domain: `farelin.com`
- Authorized JavaScript origin: `https://farelin.com`
- Authorized redirect URI:
  `https://farelin.com/backend/auth/oauth/google/callback`

That callback is derived from `AUTH_PUBLIC_BASE_URL`; changing one without the
other causes `redirect_uri_mismatch`. Keep local callback URIs registered for
local development. If Apple Sign In is enabled, update its Services ID website
and return URL to the equivalent Farelin values; do not add Apple configuration
when it is not in use.

## Travelpayouts / Aviasales

Update the existing Travelpayouts project/site name to Farelin and its domain to
`https://farelin.com`. Keep `TRAVELPAYOUTS_MARKER` unchanged unless
Travelpayouts issues a replacement. Farelin uses marker-bearing outbound HTTPS
links and does not use the Travelpayouts Drive script.

## Stripe

If billing is enabled, change customer-facing branding to Farelin and the
product name to `Farelin Pro`. Set Checkout success/cancel and Customer Portal
return URLs to the Farelin domain. Do not replace price IDs or subscriptions
merely for the rename.

## Search and indexing

1. Add a Google Search Console Domain Property for `farelin.com` and verify it
   through DNS.
2. Submit `https://farelin.com/sitemap.xml`.
3. Inspect `/`, `/discover`, and `/pricing` and verify their Farelin canonicals.
4. Request indexing for the important public pages if useful.
5. Monitor crawl, canonical, and redirect errors during the migration.

Also independently check Farelin name conflicts in EUIPO, WIPO, the Apple App
Store, Google Play, and major social platforms. This checklist is not trademark
clearance.

## Post-deploy smoke test

1. Open `https://farelin.com`; verify TLS, Farelin title/navbar/footer, canonical,
   and no console errors.
2. Open `https://www.farelin.com`; expect a permanent redirect to the apex.
3. Open an old `triplet-web.vercel.app` path with a query; expect the same path
   and query at Farelin.
4. Complete email signup, verification, password reset, and Google OAuth.
5. Refresh after OAuth and verify the session remains signed in.
6. Create and confirm a Watch, then verify an eligible fare email.
7. Reply to the email and confirm the monitored inbox receives it.
8. Click `Check live price`; verify HTTPS and the Travelpayouts marker.
9. Share the homepage and a public trip link; verify Farelin social copy and
   observed-fare wording.
10. Open `/robots.txt` and `/sitemap.xml`; verify Farelin URLs.
