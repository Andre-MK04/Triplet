"use client";

import { AppShell } from "../../components/AppShell";
import { Card } from "../../components/ui/Card";

const SECTIONS = [
  {
    icon: "🔑",
    title: "Your account",
    points: [
      "Passwords are hashed with a strong one-way algorithm — we never store or see your actual password.",
      "Sessions use httpOnly cookies, so scripts in the browser can't steal your login token.",
      "Refresh tokens rotate on every use and logging out revokes them server-side.",
      "Password resets use single-use, expiring links.",
    ],
  },
  {
    icon: "🗂",
    title: "Your data",
    points: [
      "Your travel profile (airports, budget, preferences) is used for exactly one thing: ranking trips for you.",
      "We store observed flight prices — not your browsing history.",
      "Alert emails include one-click manage and unsubscribe links; the tokens for those links are stored only as hashes.",
      "We don't sell your data and run no ad trackers. The only third-party script is Travelpayouts' affiliate attribution, which credits Triplet when you open a flight deal link.",
    ],
  },
  {
    icon: "🤖",
    title: "The AI layer",
    points: [
      "The AI never sees your password or payment details — it receives a compact summary of your preferences and real search results.",
      "The AI cannot invent prices or book anything; it can only call a small, fixed set of internal search tools.",
      "Every fare shown comes from a deterministic backend search, labeled live, cached, indicative, or demo.",
    ],
  },
  {
    icon: "💳",
    title: "Payments",
    points: [
      "When paid plans are enabled, subscription payments are processed by Stripe; card numbers never touch Triplet's servers.",
      "Triplet never charges you for flights — we don't sell or book them.",
    ],
  },
  {
    icon: "🛡",
    title: "Engineering practices",
    points: [
      "Strict input validation on every endpoint and rate limits on login, signup, and search.",
      "Provider API keys live only in backend environment variables, never in the browser.",
      "Production refuses to start with insecure defaults (dev secrets, insecure cookies, non-HTTPS URLs).",
      "Structured error responses without stack traces in production.",
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
        <p className="text-center text-xs text-mist/60">
          Found a security issue? Email us — responsible disclosure is always welcome.
        </p>
      </div>
    </AppShell>
  );
}
