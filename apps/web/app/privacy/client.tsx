"use client";

import { AppShell } from "../../components/AppShell";
import { ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";

const SECTIONS: Array<{ title: string; body: React.ReactNode }> = [
  {
    title: "What we collect and why",
    body: (
      <ul className="space-y-2">
        <li>• <strong className="text-cloud">Account</strong>: email, an optional display name, and a hashed password — to sign you in and send alerts you asked for.</li>
        <li>• <strong className="text-cloud">Travel profile</strong>: your airports, trip preferences and budget — solely to rank trips for you.</li>
        <li>• <strong className="text-cloud">Saved watches</strong>: the searches you ask us to monitor, and when we last checked them.</li>
        <li>• <strong className="text-cloud">Security logs</strong>: sign-in events and a salted, one-way hash of your IP (not your raw IP) to detect abuse.</li>
      </ul>
    ),
  },
  {
    title: "Legal basis (GDPR)",
    body: (
      <p>
        We process your account and profile data to perform the service you signed up for
        (Art. 6(1)(b)), and keep minimal security logs under our legitimate interest in
        protecting the service (Art. 6(1)(f)). We do not sell your data or use it for
        third-party advertising.
      </p>
    ),
  },
  {
    title: "Where your data lives",
    body: (
      <p>
        Your data is stored in a PostgreSQL database hosted in the EU/EEA, encrypted at rest,
        reachable only by our backend over a private network — never exposed publicly. Passwords
        and tokens are stored only as one-way hashes.
      </p>
    ),
  },
  {
    title: "Third parties",
    body: (
      <p>
        Flight prices come from <strong className="text-cloud">Travelpayouts / Aviasales</strong>. When you open a
        deal, we pass an affiliate marker so Triplet may earn a commission; their site sets its own
        cookies under its policy. Subscription payments (if you upgrade) are handled by
        <strong className="text-cloud"> Stripe</strong> — card details never touch our servers. We use no advertising
        or analytics trackers.
      </p>
    ),
  },
  {
    title: "How long we keep it",
    body: (
      <ul className="space-y-2">
        <li>• Account and profile data: until you delete your account.</li>
        <li>• Security audit logs: pruned on a rolling window and anonymised when you erase your account.</li>
        <li>• Trip suggestions and cached fares: short-lived and expire automatically.</li>
      </ul>
    ),
  },
  {
    title: "Your rights",
    body: (
      <p>
        You can <strong className="text-cloud">download all your data</strong> or
        <strong className="text-cloud"> permanently delete your account</strong> at any time from your
        Account page — deletion removes your personal data across our systems. You also have the
        right to correct your data and to lodge a complaint with your local data-protection authority.
      </p>
    ),
  },
];

export function PrivacyClient() {
  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6 pb-10">
        <header className="text-center">
          <h1 className="font-display text-4xl font-bold text-cloud">Privacy policy</h1>
          <p className="mx-auto mt-3 max-w-xl text-mist">
            Plain-language, GDPR-aligned. The short version: we collect the minimum to find you
            trips, store it securely in the EU, never sell it, and let you export or delete it anytime.
          </p>
        </header>
        {SECTIONS.map((section) => (
          <Card key={section.title}>
            <h2 className="font-display text-lg font-bold text-cloud">{section.title}</h2>
            <div className="mt-3 text-sm text-mist">{section.body}</div>
          </Card>
        ))}
        <div className="flex justify-center gap-3">
          <ButtonLink href="/account" variant="secondary">Manage your data</ButtonLink>
          <ButtonLink href="/security" variant="secondary">Security overview</ButtonLink>
        </div>
      </div>
    </AppShell>
  );
}
