"use client";

import { AppShell } from "../../components/AppShell";
import { ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { legalOperator, missingOperatorDetails } from "../../lib/legal";
import { useLegalVersions } from "../../lib/legalVersions";

function policySections(): Array<{ title: string; body: React.ReactNode }> {
  return [
  {
    title: "What we collect and why",
    body: (
      <ul className="space-y-2">
        <li>• <strong className="text-cloud">Account</strong>: email, an optional display name, a hashed password, whether the address has been confirmed, and which versions of these documents you accepted when you signed up.</li>
        <li>• <strong className="text-cloud">Sign-in with Google</strong>: the provider, your provider account ID and the email it reports. Farelin does not store provider access tokens.</li>
        <li>• <strong className="text-cloud">Travel profile</strong>: your departure airports, base location, trip length, budget and comfort preferences — used to personalize search, ranking and watch behavior.</li>
        <li>• <strong className="text-cloud">My World</strong>: the countries you mark as visited, lived in or on your wishlist, any dates you add, and your private notes. This is not public or visible to other Farelin users. Access by authorised operators is limited to what is needed to run, support and secure the service.</li>
        <li>• <strong className="text-cloud">Saved watches</strong>: the search criteria, the address to notify, the conditions that trigger an email, how often it runs, when it last ran and what was sent.</li>
        <li>• <strong className="text-cloud">Trip suggestions</strong>: trips generated for you are stored so a link keeps working, and expire on their own.</li>
        <li>• <strong className="text-cloud">Usage and plan</strong>: AI search counts, your plan, and trial status — to apply the limits your plan describes.</li>
        <li>• <strong className="text-cloud">Sessions and security logs</strong>: sign-in events, session records with the browser you used, and a one-way keyed hash of your IP address rather than the address itself.</li>
        <li>• <strong className="text-cloud">Billing</strong>: when paid plans are enabled, Stripe customer and subscription identifiers. Card numbers never reach Farelin.</li>
        <li>• <strong className="text-cloud">Contact messages</strong>: the name, email address, selected topic and message you submit pass through Farelin&apos;s API and Resend to our support mailbox. Farelin does not store their content in its PostgreSQL database. Mailbox and provider records are retained only as long as reasonably needed to answer, protect the service, meet legal obligations and resolve disputes; no fixed deletion date is promised unless it is technically enforced.</li>
      </ul>
    ),
  },
  {
    title: "Legal basis (GDPR)",
    body: (
      <ul className="space-y-2">
        <li>• <strong className="text-cloud">Service performance</strong> (Art. 6(1)(b)): accounts, travel profiles, searches, watches, alerts, transactional email and requested AI-assisted processing.</li>
        <li>• <strong className="text-cloud">Support</strong> (Art. 6(1)(b) or 6(1)(f), depending on the request): receiving and answering messages you choose to send.</li>
        <li>• <strong className="text-cloud">Security and abuse prevention</strong> (Art. 6(1)(f)): short-lived sessions, rate limits, audit records and pseudonymous email-suppression records.</li>
        <li>• <strong className="text-cloud">Billing</strong> (Art. 6(1)(b) and, where required, 6(1)(c)): subscription administration and legally required accounting records, only when paid plans are enabled.</li>
        <li>• <strong className="text-cloud">Legal obligations</strong> (Art. 6(1)(c)): records Farelin must retain or disclose under applicable law.</li>
      </ul>
    ),
  },
  {
    title: "Where your data lives",
    body: (
      <p>
        Farelin&apos;s primary account database is a PostgreSQL instance hosted in the EU/EEA
        (Amsterdam). Access requires credentials held only by our backend services, and passwords
        and tokens are stored only as one-way hashes. We do not make a public claim about storage
        encryption that our hosting provider&apos;s documentation does not substantiate. Some service
        providers we rely on — flight data, email delivery, and payments
        when paid plans are enabled — may process limited information outside the EU/EEA under
        their own contractual and legal safeguards, so we do not claim that every piece of data
        stays inside the EU at all times.
      </p>
    ),
  },
  {
    title: "Fare accuracy reports",
    body: (
      <p>
        Farelin shows fares it has observed rather than live prices. To learn how far those drift,
        it may ask whether a price still held after you followed a live-price link. Following the
        link sends nothing — the check is noted only in your browser. If you answer, what is stored
        describes the fare: the route, how old the observation was, what Farelin showed, and which
        of the four answers you chose. Nothing describes you — no account link, no address, and no
        identifier beyond a random value whose only purpose is to stop one check being answered
        twice. Farelin asks at most once a day, never twice about the same fare, and
        &ldquo;Don&rsquo;t ask again&rdquo; stops it entirely.
      </p>
    ),
  },
  {
    title: "Third parties",
    body: (
      <p>
        Flight prices come from <strong className="text-cloud">Travelpayouts / Aviasales</strong>. Transactional
        messages and contact-form delivery use <strong className="text-cloud">Resend</strong>, which receives the
        recipient address and message content needed to deliver each email. When you open a
        deal we add an affiliate marker to the link itself, so Farelin may earn a commission if you book;
        Farelin adds no fee to the fare, and the booking provider sets the price you pay. Once you
        follow that link their site applies its own policy and cookies.
        Commission does not affect how Farelin ranks results. When paid plans are enabled,
        subscription payments are handled by <strong className="text-cloud">Stripe</strong> — card details never
        touch our servers. <strong className="text-cloud">Farelin loads no third-party scripts at all</strong>: no
        advertising, no analytics, and no affiliate tracking script. Attribution travels in the
        booking link, not in code running on your browser. If operational error monitoring is
        enabled, <strong className="text-cloud">Sentry</strong> may receive redacted technical error and
        performance details; Farelin configures it without default personal-data collection. If
        Sentry is not configured, nothing is sent to it.
      </p>
    ),
  },
  {
    title: "How long we keep it",
    body: (
      <ul className="space-y-2">
        <li>• Account, profile and My World data: until you delete your account.</li>
        <li>• Email confirmation and password reset links: short-lived and single-use.</li>
        <li>• Sessions: until they expire or you log out, which revokes them.</li>
        <li>• Watches you never confirmed: removed automatically after a set period, so an address that never said yes does not sit in the database indefinitely.</li>
        <li>• Trip suggestions and cached fares: short-lived and expire automatically.</li>
        <li>• Security audit logs: pruned on a rolling window and anonymised when you erase your account.</li>
        <li>• Verified email delivery events: minimal pseudonymous delivery metadata is retained for a limited operational window.</li>
        <li>• Hard-bounce and complaint suppression records: retained as a keyed hash while needed to prevent repeat unwanted or undeliverable mail.</li>
        <li>• Support correspondence: retained in the support mailbox according to the criteria above, not a fixed application-database timer.</li>
        <li>• Fare observations: kept long-term as market data. See below.</li>
      </ul>
    ),
  },
  {
    title: "Fare history is market data",
    body: (
      <>
        <p>
          Farelin records the fares it observes — the route, the dates, the price, which source
          reported it and when. That history is what lets Farelin say whether €120 to Lisbon is
          genuinely good or merely normal, and it is the reason the product exists.
        </p>
        <p className="mt-3">
          These observations describe a market, not a person. They are not linked to your
          account, and deleting your account does not remove them, because there is nothing in
          them that is yours. Your searches, watches, profile and trips are a different matter
          and are erased with your account.
        </p>
      </>
    ),
  },
  {
    title: "What the AI sees",
    body: (
      <>
        <p>
          When you search in plain language, Farelin sends your request and the minimum
          constraints needed to search it — dates, budget, airports — to the AI provider
          configured for the service. It is never sent your password, your session, payment
          details, or your private My World notes.
        </p>
        <p className="mt-3">
          <strong className="text-cloud">Prices do not come from the AI.</strong> The model can
          interpret a request, help shape search criteria and draft an itinerary. Every fare is
          produced by Farelin&apos;s own deterministic search against provider data, and the
          model cannot invent one or book anything.
        </p>
        <p className="mt-3">
          Farelin supports more than one AI provider and uses the one configured for the
          service at the time. Ask at the support address if you need to know which is
          currently in use.
        </p>
      </>
    ),
  },
  {
    title: "Your rights",
    body: (
      <p>
        You can <strong className="text-cloud">download all your data</strong> or
        <strong className="text-cloud"> permanently delete your account</strong> at any time from your
        Account page. Farelin deletes account-linked application data and anonymises the user link
        in its limited security audit trail. Some records may remain outside that immediate flow:
        support correspondence and provider delivery logs, security records that no longer identify
        the account directly, hard-bounce or complaint suppression hashes, rotating backups, and
        billing or legal records that must be retained. You can ask us to review those records. You
        also have the right to correct your data and to lodge a complaint with your local
        data-protection authority.
      </p>
    ),
  },
  ];
}

export function PrivacyClient() {
  const versions = useLegalVersions();
  const missing = missingOperatorDetails();
  const sections = policySections();

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6 pb-10">
        <header className="text-center">
          <h1 className="font-display text-4xl font-bold text-cloud">Privacy policy</h1>
          <p className="mx-auto mt-3 max-w-xl text-mist">
            Published version {versions?.privacyVersion ?? "loading…"}. We explain what Farelin
            processes, why, who receives it, and the controls available to you.
          </p>
        </header>
        {missing.length > 0 ? (
          <Card>
            <h2 className="font-display text-lg font-bold text-cloud">Controller information incomplete</h2>
            <p className="mt-3 text-sm text-mist">
              Farelin has not yet published all required controller details ({missing.join(", ")}).
              This must be resolved before commercial public launch; no placeholder identity is shown.
            </p>
          </Card>
        ) : (
          <Card>
            <h2 className="font-display text-lg font-bold text-cloud">Controller</h2>
            <address className="mt-3 whitespace-pre-line text-sm not-italic text-mist">
              {legalOperator.name}<br />
              {legalOperator.address}<br />
              <a className="underline underline-offset-2" href={`mailto:${legalOperator.supportEmail}`}>
                {legalOperator.supportEmail}
              </a>
              {legalOperator.registrationNumber ? <><br />Registration: {legalOperator.registrationNumber}</> : null}
              {legalOperator.vatNumber ? <><br />VAT: {legalOperator.vatNumber}</> : null}
            </address>
          </Card>
        )}
        {sections.map((section) => (
          <Card key={section.title}>
            <h2 className="font-display text-lg font-bold text-cloud">{section.title}</h2>
            <div className="mt-3 text-sm text-mist">{section.body}</div>
          </Card>
        ))}
        <div className="flex justify-center gap-3">
          <ButtonLink href="/account" variant="secondary">Manage your data</ButtonLink>
          <ButtonLink href="/security" variant="secondary">Security overview</ButtonLink>
          <ButtonLink href="/contact" variant="secondary">Contact us</ButtonLink>
        </div>
      </div>
    </AppShell>
  );
}
