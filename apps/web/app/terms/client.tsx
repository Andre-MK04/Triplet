"use client";

import Link from "next/link";

import { AppShell } from "../../components/AppShell";
import { AffiliateDisclosure } from "../../components/AffiliateDisclosure";
import { Notice } from "../../components/ui/Misc";
import { legalOperator, missingOperatorDetails } from "../../lib/legal";
import { useLegalVersions } from "../../lib/legalVersions";


function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line py-8">
      <h2 className="font-display text-xl font-bold text-cloud">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-mist">{children}</div>
    </section>
  );
}

export function TermsClient() {
  const missing = missingOperatorDetails();
  const versions = useLegalVersions();

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl py-12">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
          Legal
        </p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight text-cloud">
          Terms of service
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-mist">
          Published version {versions?.termsVersion ?? "loading…"}. These terms cover using Farelin to discover trips and
          monitor fares. Plain language, because terms nobody reads protect nobody.
        </p>

        {/* Missing operator identity is a real publication gap, not a cosmetic
            development warning. Never replace it with invented details. */}
        {missing.length > 0 ? (
          <div className="mt-6">
            <Notice tone="warning">
              Farelin&apos;s published operator information is incomplete ({missing.join(", ")}).
              This must be resolved before a commercial public launch; no placeholder identity is shown.
            </Notice>
          </div>
        ) : null}

        <Section title="What Farelin is">
          <p>
            Farelin is a flight discovery service. It searches fare data for trip opportunities
            from the airports you choose, ranks them, keeps a history of the prices it has
            observed, and can watch a search and tell you when something worth seeing appears.
            It also uses AI to interpret travel requests written in ordinary language.
          </p>
          <p className="text-cloud">Farelin does not:</p>
          <ul className="space-y-1.5 pl-4">
            <li>— sell flights or issue tickets</li>
            <li>— take payment for travel</li>
            <li>— guarantee any fare, price or availability</li>
            <li>— act as an airline, travel agent or tour operator</li>
            <li>— become a party to any booking contract you enter</li>
          </ul>
          <p>
            When you book, your contract is with the airline or travel agency you book through,
            under their terms. Farelin is not part of it and cannot change, cancel or refund it.
          </p>
        </Section>

        <Section title="What the prices mean">
          <p>
            This is the most important section on this page. Farelin shows fares it has{" "}
            <strong className="text-cloud">observed</strong>, not live inventory. A price on
            Farelin is a record that a fare was seen at a point in time, which is why prices are
            shown with their age and phrased as “from”, “recently from” or “estimated from”.
          </p>
          <p>
            Prices change constantly and without notice. A fare Farelin observed hours ago may
            no longer exist. Some totals are{" "}
            <strong className="text-cloud">estimates assembled from separately observed fares</strong>{" "}
            — a multi-city chain, for instance, is the sum of its legs, each seen independently.
            Farelin labels these rather than presenting them as a single verified price.
          </p>
          <p>
            <strong className="text-cloud">
              Always confirm the actual price with the provider before booking.
            </strong>{" "}
            That is what every “Check live price” link is for. Farelin makes no promise that a
            price it displays will be available to you.
          </p>
        </Section>

        <Section title="Multi-city and open-jaw trips">
          <p>
            Trips with several stops, or that fly home from a different city, are often built
            from <strong className="text-cloud">separate tickets bought separately</strong>. Where
            that is the case, Farelin says so on the trip.
          </p>
          <p>
            Separate tickets are separate contracts. If one flight is delayed or cancelled, the
            airline operating the next one is generally under no obligation to protect, rebook or
            refund you — a protection you would normally have on a single through-ticket. Leave
            sensible margins, and check each airline&apos;s terms.
          </p>
          <p>
            Travel between cities that Farelin does not book for you — trains, buses, ferries,
            driving — is never included in a trip price. Where Farelin estimates such a crossing
            it is for planning only, and arranging it is up to you.
          </p>
        </Section>

        <Section title="AI-assisted search">
          <p>
            Farelin uses an AI model to interpret what you type into search and to help assemble
            itineraries. It turns a request into search criteria — origins, destinations, dates,
            budget, trip shape.
          </p>
          <p>
            <strong className="text-cloud">
              Prices and flight details never come from the AI model.
            </strong>{" "}
            They come from fare data and Farelin&apos;s own observations. The model chooses what
            to search for; it does not invent what things cost.
          </p>
          <p>
            AI output can still be wrong — a misread date, a city confused for another, a
            suggestion that does not suit you. Check that a trip is what you actually want before
            acting on it, and verify anything that matters independently.
          </p>
        </Section>

        <Section title="Your responsibilities">
          <p>
            Farelin finds trip ideas. Whether a trip is one you can legally and practically take
            is yours to establish. That includes:
          </p>
          <ul className="space-y-1.5 pl-4">
            <li>— passports, visas and entry requirements for every country involved</li>
            <li>— transit rules for airports you connect through</li>
            <li>— health, vaccination and travel restrictions</li>
            <li>— baggage allowances, fees and what a fare actually includes</li>
            <li>— connection times, especially between separate tickets</li>
            <li>— travel between airports and cities, and how long it takes</li>
            <li>— travel insurance</li>
          </ul>
          <p>
            Farelin does not check any of this for you and cannot be relied on for it.
          </p>
        </Section>

        <Section title="Accounts and acceptable use">
          <p>
            You are responsible for keeping your account credentials secure and for what happens
            under your account. Tell us promptly if you think it has been compromised.
          </p>
          <p>Please do not:</p>
          <ul className="space-y-1.5 pl-4">
            <li>— scrape, crawl or bulk-extract Farelin&apos;s data</li>
            <li>— attempt to bypass rate limits, quotas or access controls</li>
            <li>— probe, attack or disrupt the service or its infrastructure</li>
            <li>— set up fare watches for email addresses that are not yours</li>
            <li>— resell or redistribute Farelin&apos;s results as your own service</li>
          </ul>
          <p>
            We may suspend or close accounts that do these things, or that put the service or
            other users at risk.
          </p>
        </Section>

        <Section title="Affiliate links and how Farelin is funded">
          <AffiliateDisclosure className="text-sm text-mist" />
          <p>
            When you follow a booking link, an identifier travels with it so the booking site
            knows the visit came from Farelin. If you then book, Farelin may receive a commission
            from that site. Farelin adds nothing to the fare — what you pay is set by the booking
            provider, and their price and availability can differ from what Farelin last observed.
          </p>
          <p>
            Ranking is calculated from trip quality, price, how recently the fare was observed,
            how it compares with prices Farelin has recorded before, and how well it fits your
            travel profile. Whether a result earns commission is not one of the inputs, and
            Farelin has automated tests that fail if it becomes one.
          </p>
        </Section>

        <Section title="Paid plans">
          <p>
            Farelin&apos;s core discovery is free to use. Where paid plans are offered, what each
            includes and costs is shown on the{" "}
            <Link href="/pricing" className="text-mint underline hover:text-cloud">
              pricing page
            </Link>{" "}
            before you pay, and payment is handled by Stripe — card details never reach Farelin.
            You can cancel at any time and keep access until the end of the period you have paid
            for.
          </p>
        </Section>

        <Section title="Availability and liability">
          <p>
            Farelin is a small service, provided as-is and as-available. It may be unavailable,
            interrupted, or wrong. Fare data comes from third parties and may be incomplete,
            delayed or inaccurate, and Farelin does not warrant that any result is accurate,
            current or suitable for you.
          </p>
          <p>
            To the fullest extent the law allows, Farelin is not liable for losses arising from
            using it — including fares that changed or disappeared, trips that could not be
            booked, missed connections between separate tickets, or decisions taken on the basis
            of a result or an AI-generated suggestion. Nothing here limits liability that cannot
            legally be limited, and if you are a consumer your statutory rights are unaffected.
          </p>
        </Section>

        <Section title="Changes to these terms">
          <p>
            These terms may change as Farelin changes. The published version at the top identifies
            the document shown during signup. Material changes are versioned and communicated as
            applicable; typo and formatting fixes do not trigger a new acceptance record.
          </p>
        </Section>

        <Section title="Who operates Farelin">
          {legalOperator.name || legalOperator.supportEmail || legalOperator.address ? (
            <>
              {legalOperator.name ? (
                <p className="text-cloud">{legalOperator.name}</p>
              ) : null}
              {legalOperator.address ? (
                <p className="whitespace-pre-line">{legalOperator.address}</p>
              ) : null}
              {legalOperator.registrationNumber ? (
                <p>Company registration: {legalOperator.registrationNumber}</p>
              ) : null}
              {legalOperator.vatNumber ? <p>VAT: {legalOperator.vatNumber}</p> : null}
              {legalOperator.supportEmail ? (
                <p>
                  Contact:{" "}
                  <a
                    href={`mailto:${legalOperator.supportEmail}`}
                    className="text-mint underline hover:text-cloud"
                  >
                    {legalOperator.supportEmail}
                  </a>
                </p>
              ) : null}
            </>
          ) : (
            <p>
              Farelin&apos;s legal operator identity and establishment address have not yet been
              published. The brand name alone does not identify the controller. This must be
              completed before commercial public launch after appropriate Slovenian legal advice.
            </p>
          )}
          <p>
            See the{" "}
            <Link href="/privacy" className="text-mint underline hover:text-cloud">
              privacy policy
            </Link>{" "}
            for how Farelin handles your data, and{" "}
            <Link href="/security" className="text-mint underline hover:text-cloud">
              security
            </Link>{" "}
            for how it is protected.
          </p>
        </Section>
      </div>
    </AppShell>
  );
}
