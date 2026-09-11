# Farelin Stripe launch runbook

Farelin sells access to Farelin Pro. It does not sell flights. Complete this
runbook in Stripe test mode before creating the equivalent live-mode objects.

## 1. Business and customer-facing settings

In Stripe, set the public business name to `Farelin` and add:

- website: `https://www.farelin.com`
- support email: the monitored Farelin support address
- privacy policy: `https://www.farelin.com/privacy`
- terms: `https://www.farelin.com/terms`
- statement descriptor and customer support details

Configure Stripe's customer emails for successful payments, failed payments,
and upcoming renewals as appropriate. These are billing communications; Farelin's
Resend alert service is not a replacement for them.

## 2. Product and recurring prices (test mode)

Create one active product:

```text
Name: Farelin Pro
Description: Daily fare checks, 100 AI searches per month, 10 saved watches,
             8 origin airports, open-jaw suggestions, and deal and fit scores.
```

Create exactly two EUR recurring prices on that product:

```text
Monthly: EUR 6.99, recurring every month
Yearly:  EUR 49.00, recurring every year
```

Copy their `price_...` IDs. A test price belongs with a test secret key; live
mode needs newly created live prices. Stripe price amounts cannot be edited
after creation, so archive a mistake and create a replacement.

If Managed Payments is enabled, set an eligible tax code on the `Farelin Pro`
product and keep the integration on Stripe API `2025-03-31.basil` or newer.
Stripe rejects Checkout before payment when either requirement is missing.

Decide whether the displayed prices include tax before live launch. Farelin can
enable Stripe Tax with `STRIPE_AUTOMATIC_TAX_ENABLED=true`, but only after the
business has configured its actual tax registrations and confirmed the displayed
consumer prices with a qualified accountant. Do not turn it on merely because
the switch exists.

## 3. Customer Portal (test mode)

Activate the Customer Portal and configure it to allow:

- payment-method updates
- invoice-history access
- subscription cancellation

Use `https://www.farelin.com/dashboard` as the default return URL. Farelin has
only one paid product at launch, so leave product switching off unless monthly ↔
yearly switching and its proration behavior have been deliberately tested.

## 4. Signed webhook (test mode)

Create a Stripe webhook/event destination pointing directly at the Railway API:

```text
https://triplet-production.up.railway.app/billing/webhook
```

The direct API URL avoids making Stripe delivery depend on the Vercel frontend
proxy. Subscribe to:

```text
checkout.session.completed
checkout.session.async_payment_succeeded
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
invoice.paid
invoice.payment_failed
```

Copy the endpoint's `whsec_...` signing secret. It is not the Stripe API key.
Farelin verifies the signature over the raw request body, records event IDs for
idempotency, and returns a non-2xx response when processing fails so Stripe can
retry.

## 5. Railway API variables (test mode)

Add these to the API service only. The hourly alerts/cron service does not call
Stripe and does not need Stripe secrets.

```text
BILLING_PROVIDER=stripe
STRIPE_SECRET_KEY=<test sk_test_... or least-privilege test restricted key>
STRIPE_WEBHOOK_SECRET=<test endpoint whsec_...>
STRIPE_PRICE_PRO_MONTHLY=<test monthly price_...>
STRIPE_PRICE_PRO_YEARLY=<test yearly price_...>
STRIPE_API_VERSION=2025-03-31.basil
# Set false only if Farelin deliberately stops using Stripe as merchant of record.
STRIPE_MANAGED_PAYMENTS_ENABLED=true
STRIPE_AUTOMATIC_TAX_ENABLED=false
BILLING_SUCCESS_URL=https://www.farelin.com/billing/success
BILLING_CANCEL_URL=https://www.farelin.com/pricing
BILLING_PORTAL_RETURN_URL=https://www.farelin.com/dashboard
```

`STRIPE_PUBLISHABLE_KEY` is not needed by the current Stripe-hosted Checkout
flow. Never add `STRIPE_SECRET_KEY` or `STRIPE_WEBHOOK_SECRET` to Vercel, a
`NEXT_PUBLIC_*` variable, source control, screenshots, or support messages.

Set `BILLING_ENABLED=true` only after every value above is present. Production
startup deliberately refuses a half-configured billing deployment.

## 6. Test-mode acceptance run

Use a verified Farelin account that is not already Pro:

1. Open `/pricing` and start monthly Checkout.
2. Complete Stripe test Checkout.
3. Confirm `/billing/success` changes from “Confirming your plan” to “Farelin Pro is active”.
4. Refresh `/dashboard`; confirm the Pro limits are visible.
5. Open Manage billing; confirm the portal shows the test subscription.
6. Cancel at period end; confirm Farelin still grants Pro until the period ends.
7. In Stripe Workbench, confirm webhook deliveries return HTTP 200.
8. Repeat with a second verified Farelin account and the yearly price.
9. Run Stripe's failed-payment test and confirm the dashboard exposes the payment problem and links to Manage billing.
10. Confirm a Pro account cannot create a second Checkout session by calling the endpoint again.

Also resend one webhook from Stripe Workbench. The duplicate must return 200
without creating another subscription row or changing usage twice.

## 7. Live-mode cutover

Only after the test-mode acceptance run passes:

1. Complete Stripe account activation and business verification.
2. Create the live Farelin Pro product and both live recurring prices.
3. Configure the live Customer Portal.
4. Create a live webhook endpoint with the same event list.
5. Replace all four test values in Railway together: API key, webhook secret,
   monthly price, yearly price.
6. Redeploy and confirm `/backend/billing/plans` reports billing enabled.
7. Make one real low-risk purchase, verify the invoice and entitlement, then
   cancel/refund it according to the intended support procedure.

Keep the test objects for staging. Never point production at a mixture of test
and live objects.

## Honest limits

- Stripe handles card data; Farelin stores Stripe customer/subscription IDs and
  status, not card numbers.
- Stripe integration does not decide VAT registrations, consumer withdrawal
  rights, invoice wording, or accounting treatment. A qualified EU accountant
  or lawyer must make those calls before commercial launch.
- Webhooks are asynchronous. The success page waits briefly and then explains a
  delay instead of granting Pro from a browser redirect.
