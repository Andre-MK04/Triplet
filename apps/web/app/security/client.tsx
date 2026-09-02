"use client";

import { AppShell } from "../../components/AppShell";
import { Card } from "../../components/ui/Card";

const SECTIONS = [
  {
    icon: "🔑",
    title: "Your account",
    points: [
      "Passwords are hashed with Argon2id. Accounts created before that use PBKDF2 and are upgraded automatically the next time you log in — no reset, nothing to do.",
      "Sessions use httpOnly cookies, so scripts in the browser cannot read your login token.",
      "Refresh tokens are stored only as hashes, rotate on every use, and are revoked server-side when you log out.",
      "State-changing requests carry a CSRF token, so another site cannot act as you using your cookies.",
      "Password resets and email confirmations use single-use links that expire. Both are stored only as hashes, so a database copy does not yield working links.",
      "Confirming your email address is what lets Triplet send fare alerts to it. Until then, a watch on that address asks the address itself to confirm.",
    ],
  },
  {
    icon: "🗂",
    title: "Your data",
    points: [
      "Your travel profile — airports, budget, preferences — personalizes Triplet's search, ranking and watch behavior.",
      "Triplet stores observed flight prices, not your browsing history.",
      "Alert emails include one-click manage and unsubscribe links; those tokens are stored only as hashes.",
      "Triplet does not sell your data, and loads no advertising or affiliate-tracking scripts. Affiliate attribution is carried in the outbound booking link itself.",
      "Logs are redacted before they are written: credentials, tokens and anything credential-shaped are stripped, including inside stack traces.",
    ],
  },
  {
    icon: "🤖",
    title: "The AI layer",
    points: [
      "The AI never sees your password or payment details. It receives your request and a compact summary of the preferences needed to search.",
      "The AI cannot invent prices or book anything. It can only call a small, fixed set of internal search tools.",
      "Every fare comes from a deterministic backend search, never from the model, and is labeled with how it was obtained and when it was observed.",
      "AI usage is capped per account and in total per day, so a runaway loop cannot spend without limit.",
    ],
  },
  {
    icon: "💳",
    title: "Payments",
    points: [
      "When paid plans are enabled, subscriptions are processed by Stripe. Card numbers never touch Triplet's servers.",
      "Triplet never charges you for flights — it does not sell or book them.",
    ],
  },
  {
    icon: "🛡",
    title: "Engineering practices",
    points: [
      "Every endpoint validates its input, and rate limits are applied by cost: cheap lookups, searches, AI calls, authentication and alert creation each have their own ceiling.",
      "Rate limiting is shared across instances through Redis. If Redis becomes unreachable it falls back to per-process limits rather than failing open, and retries.",
      "Provider API keys live only in backend environment variables, never in the browser.",
      "Production refuses to start with genuinely unsafe configuration — a development secret, insecure cookies, or a non-HTTPS URL.",
      "Errors return structured responses without stack traces in production.",
      "Every push runs the test suite, a dependency vulnerability audit, and a scan for committed secrets or database files.",
    ],
  },
];

export function SecurityClient() {
  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6 pb-10">
        <header className="text-center">
          <h1 className="font-display text-4xl font-bold text-cloud">Security &amp; privacy</h1>
          <p className="mx-auto mt-3 max-w-xl text-mist">
            Plain-language answers about how Triplet protects your account and data. No legal maze — if
            something here is unclear, that's a bug too.
          </p>
        </header>
        {SECTIONS.map((section) => (
          <Card key={section.title}>
            <h2 className="flex items-center gap-2 font-display text-lg font-bold text-cloud">
              <span aria-hidden>{section.icon}</span> {section.title}
            </h2>
            <ul className="mt-3 space-y-2 text-sm text-mist">
              {section.points.map((point) => (
                <li key={point} className="flex gap-2">
                  <span className="text-mint" aria-hidden>•</span>
                  {point}
                </li>
              ))}
            </ul>
          </Card>
        ))}
        <p className="text-center text-xs text-mist-dim">
          Found a security issue? Email us — responsible disclosure is always welcome.
        </p>
      </div>
    </AppShell>
  );
}
