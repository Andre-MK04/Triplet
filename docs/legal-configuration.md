# Legal operator configuration

Farelin's Terms page names whoever operates the service. Those details live in
configuration, and **nothing in the codebase invents them** — no placeholder
company name, registration number, VAT number or address exists anywhere, and
none should be added. Publishing a registration that does not exist is worse
than publishing none, and placeholders have a way of surviving to production.

Where a value is absent the Terms page omits that line rather than filling it.
With none set the public pages say plainly that the operator identity is
incomplete. This is a **MANUAL LEGAL DECISION REQUIRED** before commercial
public launch, not something code can solve by inventing a company or treating
the brand name as a legal person.

## Variables

Set these on the frontend deployment (Vercel). They are `NEXT_PUBLIC_` on
purpose: legal operator details are meant to be read by anyone using the
service, so they are the opposite of a secret.

| Variable | Example | Needed when |
|---|---|---|
| `NEXT_PUBLIC_LEGAL_OPERATOR_NAME` | Your actual legal name or registered business name | Required to identify the operator/controller |
| `NEXT_PUBLIC_LEGAL_SUPPORT_EMAIL` | An address you actively monitor | Required electronic contact channel |
| `NEXT_PUBLIC_LEGAL_ADDRESS` | Your lawful establishment/service address | Required where applicable; obtain Slovenian advice before publishing a home address |
| `NEXT_PUBLIC_LEGAL_REGISTRATION_NUMBER` | Your real registration number | Only when one exists and disclosure is required |
| `NEXT_PUBLIC_LEGAL_VAT_NUMBER` | Your real VAT identifier | Only when VAT registered and disclosure is required |

The Terms and Privacy pages show a warning when the operator name, support email,
or address is unset. This is intentional: silently publishing a legal notice
that cannot identify its operator would be more misleading than exposing the
configuration gap. Resolve the warning before inviting external users.

## What you need before public/commercial launch

Slovenia's ZEPT Article 5 requires an information-society service provider to
make the provider/business and establishment, working electronic contact,
registration and tax details (where applicable) easily and permanently
accessible. GDPR Article 13 separately requires the controller's identity and
contact details. Whether this specific pre-revenue/affiliate deployment is
already an economic information-society service is a legal decision for a
Slovenian professional, not a software default.

Before open commercial launch or enabling Stripe, set
`NEXT_PUBLIC_LEGAL_OPERATOR_NAME` and `NEXT_PUBLIC_LEGAL_SUPPORT_EMAIL`, plus
`NEXT_PUBLIC_LEGAL_ADDRESS` and the registration and VAT numbers if you have
incorporated. This is a prompt to check your own obligations, not legal advice.

## Consumer rights

The Terms page states that statutory consumer rights are unaffected and that
liability which cannot legally be limited is not limited. Leave those in. If you
incorporate, have the page reviewed against the law where you are established —
distance-selling and withdrawal rules differ, and Farelin's own position (it
sells nothing and is not party to the booking) is what keeps the current wording
short.

If publishing a home address creates a personal-safety concern, obtain advice
on an appropriate lawful business/service address. Do not omit a legally
required address merely because it is uncomfortable to publish.
