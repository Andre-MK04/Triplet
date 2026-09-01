# Legal operator configuration

Triplet's Terms page names whoever operates the service. Those details live in
configuration, and **nothing in the codebase invents them** — no placeholder
company name, registration number, VAT number or address exists anywhere, and
none should be added. Publishing a registration that does not exist is worse
than publishing none, and placeholders have a way of surviving to production.

Where a value is absent the Terms page omits that line rather than filling it.
With none set it says plainly that Triplet is operated as a personal project
rather than a registered company, which is accurate for an unincorporated
service and is not a gap you must close before launching.

## Variables

Set these on the frontend deployment (Vercel). They are `NEXT_PUBLIC_` on
purpose: legal operator details are meant to be read by anyone using the
service, so they are the opposite of a secret.

| Variable | Example | Needed when |
|---|---|---|
| `NEXT_PUBLIC_LEGAL_OPERATOR_NAME` | `Triplet Labs OÜ` | You trade under a company or business name |
| `NEXT_PUBLIC_LEGAL_SUPPORT_EMAIL` | `support@triplet.example` | Always recommended — it is how users reach you |
| `NEXT_PUBLIC_LEGAL_ADDRESS` | `Sepapaja 6, 15551 Tallinn, Estonia` | You are a registered business |
| `NEXT_PUBLIC_LEGAL_REGISTRATION_NUMBER` | `16123456` | Your jurisdiction requires it on published terms |
| `NEXT_PUBLIC_LEGAL_VAT_NUMBER` | `EE102345678` | You are VAT registered |

In development the Terms page shows a warning naming any of name, support email
or address that are unset. That warning is never rendered in production — users
should not be shown a note about our own configuration.

## What you need before charging money

The current defaults are appropriate for a free service run by an individual.
Before enabling Stripe and taking payment, most EU jurisdictions expect a
published legal identity and a working contact address, so at minimum set
`NEXT_PUBLIC_LEGAL_OPERATOR_NAME` and `NEXT_PUBLIC_LEGAL_SUPPORT_EMAIL`, plus
`NEXT_PUBLIC_LEGAL_ADDRESS` and the registration and VAT numbers if you have
incorporated. This is a prompt to check your own obligations, not legal advice.

## Consumer rights

The Terms page states that statutory consumer rights are unaffected and that
liability which cannot legally be limited is not limited. Leave those in. If you
incorporate, have the page reviewed against the law where you are established —
distance-selling and withdrawal rules differ, and Triplet's own position (it
sells nothing and is not party to the booking) is what keeps the current wording
short.
