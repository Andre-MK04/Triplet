# Farelin production email

Farelin sends through the existing SMTP adapter. Resend is the intended SMTP
service; it is not a separate `EMAIL_PROVIDER` implementation.

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

`alerts@farelin.com` only needs to be an authenticated sender. Resend SMTP does
not create an inbox for it. `hello@farelin.com` must be a mailbox or forwarding
route that somebody actually reads, including for support and privacy requests.

## 3. Configure Railway shared variables

Create shared/reference variables and attach them to **both** the API service
and the existing alerts scheduler service:

```text
APP_NAME=Farelin
EMAIL_PROVIDER=smtp
EMAIL_REQUIRE_REAL_PROVIDER=true
EMAIL_FROM=alerts@farelin.com
EMAIL_REPLY_TO=hello@farelin.com
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<Resend API key>
SMTP_USE_TLS=true
FRONTEND_URL=https://farelin.com
ALERTS_PUBLIC_BASE_URL=https://farelin.com
```

Keep `SMTP_PASSWORD` secret. Never put it in Vercel, `NEXT_PUBLIC_*`, logs, or
the repository. The implementation uses `smtplib.SMTP`, then `STARTTLS`, so port
587 is intentional. Port 465 would require a deliberate move to `SMTP_SSL`.

The API needs these settings for account verification, password reset, and
anonymous Watch confirmation. The alerts scheduler needs them for fare alerts.
If the scheduler cannot resolve a delivering SMTP provider, it skips the alert
pass rather than consuming Watch cooldowns. With strict email enabled this also
marks the scheduled tick as failed so the deployment can alert on it.

## 4. Redeploy and verify

1. Redeploy the Farelin API.
2. Confirm startup logs contain the reduced `email.readiness` event with
   provider `smtp`, `configured=true`, `delivers=true`, and from-domain
   `farelin.com`. It never includes the password or SMTP username.
3. Redeploy the alerts scheduler and confirm no no-delivery warning appears.
4. Create a test account and receive its verification email.
5. Request a password reset and verify its link begins with `https://farelin.com`.
6. Create and confirm a Watch.
7. Run or await a real eligible Watch alert.
8. Reply to a message and confirm it reaches `hello@farelin.com`.

When testing an alternate address, the save response now distinguishes a watch
that needs confirmation from a confirmation message accepted by SMTP. “Accepted”
means the mail server took responsibility for it; inbox placement can still be
affected by DNS, bounces, spam filtering, or the recipient mailbox. Check the
Resend delivery log for the final delivery/bounce state.

Automated tests use an in-process fake SMTP object and never send external mail.
