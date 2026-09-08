# Farelin production email

Farelin uses Resend's HTTPS API in production. Railway disables outbound SMTP
on Free, Trial, and Hobby plans, so valid SMTP credentials can still time out
there. The HTTPS adapter avoids that platform restriction and is also the route
Railway recommends for transactional mail.

Existing deployments configured with `EMAIL_PROVIDER=smtp`,
`SMTP_HOST=smtp.resend.com`, `SMTP_USERNAME=resend`, and a Resend API key in
`SMTP_PASSWORD` are detected and routed over HTTPS automatically. This bridge
restores delivery without a flag day; move to the explicit variables below so
the dashboard describes the transport Farelin is actually using.

## 1. Verify the sending domain in Resend

1. Add `farelin.com` in the Resend dashboard.
2. Add the exact DNS records Resend displays for SPF and DKIM.
3. Wait for Resend to report the domain as verified.
4. Add a DMARC record using a monitoring policy such as `p=none` initially.
5. Review reports before tightening the DMARC policy.

Resend's shared `resend.dev` test sender is restricted to the Resend account
owner's address. It cannot prove alternate-email verification works. Sending a
confirmation to any other address requires the verified `farelin.com` domain
and an `EMAIL_FROM` address on that domain.

Do not copy record values from this repository: selectors and verification
values are account-specific. Resend's dashboard is the source of truth.

## 2. Provide a real reply inbox

`alerts@farelin.com` only needs to be an authenticated sender. Resend does
not create an inbox for it. `hello@farelin.com` must be a mailbox or forwarding
route that somebody actually reads, including for support and privacy requests.

## 3. Configure Railway shared variables

Create shared/reference variables and attach them to **both** the API service
and the existing alerts scheduler service:

```text
APP_NAME=Farelin
EMAIL_PROVIDER=resend
EMAIL_REQUIRE_REAL_PROVIDER=true
EMAIL_FROM=alerts@farelin.com
EMAIL_REPLY_TO=hello@farelin.com
CONTACT_EMAIL_TO=hello@farelin.com
RESEND_API_KEY=<Resend API key>
RESEND_WEBHOOK_SECRET=<Resend webhook signing secret>
FRONTEND_URL=https://www.farelin.com
ALERTS_PUBLIC_BASE_URL=https://www.farelin.com
```

Keep `RESEND_API_KEY` secret. Never put it in Vercel, `NEXT_PUBLIC_*`, logs, or
the repository. `RESEND_WEBHOOK_SECRET` is a different secret: copy it from the
Resend webhook configuration and protect it the same way. Farelin sends from the Railway backend to Resend over HTTPS;
the key is never returned to the browser.

The API needs these settings for account verification, password reset,
anonymous Watch confirmation, and the public contact form. The alerts scheduler
needs them for fare alerts. Contact submissions are sent directly to
`CONTACT_EMAIL_TO` and are not stored in the application database. If that
variable is unset, Farelin uses the monitored `EMAIL_REPLY_TO` inbox.
If the scheduler cannot resolve a delivering SMTP provider, it skips the alert
pass rather than consuming Watch cooldowns. With strict email enabled this also
marks the scheduled tick as failed so the deployment can alert on it.

## 4. Redeploy and verify

1. Redeploy the Farelin API.
2. Confirm startup logs contain the reduced `email.readiness` event with
   provider `resend`, `configured=true`, `delivers=true`, and from-domain
   `farelin.com`. It never includes the password or SMTP username.
3. Redeploy the alerts scheduler and confirm no no-delivery warning appears.
4. Create a test account and receive its verification email.
5. Request a password reset and verify its link begins with `https://www.farelin.com`.
6. Create and confirm a Watch.
7. Run or await a real eligible Watch alert.
8. Reply to a message and confirm it reaches `hello@farelin.com`.
9. Send one contact-form message and confirm it reaches `CONTACT_EMAIL_TO`.

## 5. Configure verified delivery events

1. In Resend, create a webhook for
   `https://www.farelin.com/backend/webhooks/resend`.
2. Subscribe to `email.delivered`, `email.delivery_delayed`, `email.failed`,
   `email.bounced`, and `email.complained`.
3. Copy its signing secret into `RESEND_WEBHOOK_SECRET` on the API service.
   The alerts scheduler does not receive webhooks and does not need this value.
4. Redeploy the API and confirm `email.readiness` reports
   `deliveryWebhookConfigured=true` without exposing the secret.
5. Use Resend's webhook test controls, then confirm invalid signatures receive
   400 and duplicate event IDs do not create duplicate records.
6. Confirm a permanent bounce prevents repeat account and watch mail, while a
   complaint immediately suppresses optional watch mail.

When testing an alternate address, the save response distinguishes a watch that
needs confirmation from a confirmation message accepted by Resend. “Accepted”
means the provider took responsibility for it; inbox placement can still be
affected by DNS, bounces, spam filtering, or the recipient mailbox. Check the
Resend delivery log for the final delivery/bounce state.

Automated tests replace both HTTP and SMTP transports and never send external mail.
