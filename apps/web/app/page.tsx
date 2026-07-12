"use client";

import { motion, useReducedMotion } from "framer-motion";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { ScoreDial } from "../components/ScoreDial";
import type { GlobeMarker } from "../components/RouteGlobe";
import { ButtonLink } from "../components/ui/Button";
import { apiPost } from "../lib/api";
import { formatPrice } from "../lib/format";
import type { TripOption, TripSearchResponse } from "../lib/types";

const RouteGlobe = dynamic(() => import("../components/RouteGlobe"), { ssr: false });

const HOME_AIRPORTS = ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"];

function isoDaysFromNow(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function boardDate(iso: string): string {
  return new Date(iso)
    .toLocaleDateString("en-GB", { month: "short", day: "2-digit" })
    .toUpperCase();
}

function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const reducedMotion = useReducedMotion();
  if (reducedMotion) return <>{children}</>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

/** Real cached deals for the departures board + globe price tags. */
function useLiveDeals() {
  const [deals, setDeals] = useState<TripOption[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "offline">("loading");

  useEffect(() => {
    apiPost<TripSearchResponse>("/trips/search", {
      originAirports: HOME_AIRPORTS,
      destinationAirports: null,
      startDate: isoDaysFromNow(7),
      endDate: isoDaysFromNow(75),
      minTripLengthDays: 3,
      maxTripLengthDays: 8,
      maxBudget: 250,
      maxGroundTransferHours: 4,
      tripStyle: "surprise me",
      directOnly: false,
    })
      .then((data) => {
        setDeals(data.trips.slice(0, 6));
        setStatus(data.trips.length > 0 ? "ready" : "offline");
      })
      .catch(() => setStatus("offline"));
  }, []);

  const markers = useMemo<GlobeMarker[]>(() => {
    const seen = new Set<string>();
    const tags: GlobeMarker[] = [];
    for (const deal of deals) {
      const code = deal.outboundFlight.destination;
      if (seen.has(code)) continue;
      seen.add(code);
      tags.push({ code, label: `${code} ${formatPrice(deal.totalPrice)}` });
      if (tags.length >= 4) break;
    }
    return tags;
  }, [deals]);

  return { deals, status, markers };
}

function HeroSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = query.trim();
    router.push(q ? `/discover?q=${encodeURIComponent(q)}` : "/discover");
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-3">
      <label className="flex-1">
        <span className="sr-only">Describe the trip you want</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="somewhere warm in August, under €150"
          className="cmd-input w-full py-3 font-mono text-sm text-cloud placeholder:text-mist/50"
        />
      </label>
      <button
        type="submit"
        aria-label="Search trips"
        className="border-b border-line pb-3 font-mono text-xl leading-none text-mint transition-colors hover:text-cloud"
      >
        →
      </button>
    </form>
  );
}

function DeparturesBoard({ deals, status }: { deals: TripOption[]; status: "loading" | "ready" | "offline" }) {
  return (
    <section className="py-24">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-3">
        <div>
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Departures board
          </h2>
          <p className="mt-1 font-mono text-sm text-cloud">Live from the cache — optimized for spontaneity</p>
        </div>
        <p className="font-mono text-[10px] uppercase tracking-label text-mist/70">
          Refreshed hourly · indicative
        </p>
      </div>

      {status === "loading" ? (
        <p className="border-b border-line py-10 text-center font-mono text-[11px] uppercase tracking-label text-mist">
          Scanning fares…
        </p>
      ) : null}

      {status === "offline" ? (
        <p className="border-b border-line py-10 text-center font-mono text-[11px] uppercase tracking-label text-mist">
          Departures feed offline —{" "}
          <Link href="/discover" className="text-mint hover:text-cloud">
            search directly
          </Link>
        </p>
      ) : null}

      {status === "ready" ? (
        <div>
          {deals.map((deal) => {
            const href = deal.suggestionId ? `/trip/${deal.suggestionId}` : "/discover";
            return (
              <Link
                key={deal.id}
                href={href}
                className="group grid grid-cols-2 items-center gap-x-4 gap-y-3 border-b border-line py-5 transition-colors hover:bg-mint/5 sm:grid-cols-[minmax(0,4fr)_minmax(0,3fr)_minmax(0,2fr)_minmax(0,2fr)_minmax(0,2fr)]"
              >
                <span className="flex items-center gap-2 font-display text-2xl font-bold text-cloud">
                  {deal.outboundFlight.origin}
                  <span aria-hidden className="text-base font-normal text-mist">
                    →
                  </span>
                  {deal.outboundFlight.destination}
                </span>
                <span className="mono-num text-right font-mono text-sm text-cloud sm:text-left">
                  {boardDate(deal.outboundFlight.departureDateTime)} — {boardDate(deal.returnFlight.departureDateTime)}
                </span>
                <span className="mono-num font-mono text-sm text-mist">
                  {deal.nights} nights
                </span>
                <span className="justify-self-end sm:justify-self-start">
                  <ScoreDial value={deal.score} tone="gold" label="Deal" />
                </span>
                <span className="text-right">
                  <span className="mono-num block font-display text-3xl font-bold leading-none text-coral">
                    {formatPrice(deal.totalPrice)}
                  </span>
                  <span className="mt-1 block font-mono text-[10px] uppercase tracking-label text-mist/70">
                    Round trip · indicative
                  </span>
                </span>
              </Link>
            );
          })}
          <div className="flex justify-end pt-4">
            <Link
              href="/discover"
              className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist transition-colors hover:text-mint"
            >
              View full radar ↗
            </Link>
          </div>
        </div>
      ) : null}
    </section>
  );
}

const methodology = [
  {
    step: "01 / Input",
    title: "Command your intent.",
    text: "Forget rigid calendars. Say it in plain language — budget, vibe, rough dates — or fine-tune every knob. Triplet turns it into a real search across your home airports.",
  },
  {
    step: "02 / Monitor",
    title: "Patient surveillance.",
    text: "Every hour, Triplet refreshes cached fares from your origin airports and scores each against the route's observed history. Cheap is measured against reality, not an inflated anchor.",
  },
  {
    step: "03 / Execute",
    title: "Fly when it's worth it.",
    text: "A quiet email when a fare is unusually good for you — as a complete trip idea with a transparent score, not a countdown timer.",
  },
];

export default function LandingPage() {
  const { deals, status, markers } = useLiveDeals();

  return (
    <AppShell wide>
      {/* Hero: editorial left column, globe bleeding off the right edge. */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-14 sm:px-6 lg:min-h-[78vh] lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:pb-24 lg:pt-10">
          <div className="relative z-10 max-w-xl">
            <p className="mb-6 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
              Trip-first flight watching
            </p>
            <h1 className="font-display text-6xl font-extrabold leading-[1.05] tracking-tight text-cloud sm:text-7xl">
              Europe,
              <br />
              on a whim.
            </h1>
            <p className="mt-7 max-w-md font-display text-xl font-medium leading-relaxed text-mist">
              Tell us roughly what you want. Triplet watches the fares from your airports and tells you
              when it&apos;s worth flying.
            </p>
            <div className="mt-10">
              <HeroSearch />
              <p className="mt-4 font-mono text-[10px] uppercase tracking-label text-mist/60">
                Fares refreshed hourly · indicative, never guaranteed
              </p>
            </div>
            <p className="mt-8">
              <Link
                href="/signup"
                className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist transition-colors hover:text-mint"
              >
                Or create a travel profile →
              </Link>
            </p>
          </div>

          <div className="relative h-[340px] sm:h-[420px] lg:h-[620px]" aria-hidden>
            <div className="absolute -right-24 top-1/2 aspect-square h-[115%] -translate-y-1/2 sm:-right-16 lg:-right-56">
              <RouteGlobe markers={markers} />
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <DeparturesBoard deals={deals} status={status} />

        {/* Methodology */}
        <section className="border-t border-line py-24">
          <Reveal>
            <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint">Methodology</p>
            <h2 className="mt-4 max-w-xl font-display text-4xl font-bold text-cloud sm:text-5xl">
              Instrumental precision.
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-10 md:grid-cols-3 md:gap-8">
            {methodology.map((item, index) => (
              <Reveal key={item.step} delay={index * 0.1}>
                <div className="border-t border-line pt-5">
                  <p className="mono-num font-mono text-sm font-medium text-mint">{item.step.toUpperCase()}</p>
                  <h3 className="mt-4 font-display text-2xl font-medium text-cloud">{item.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-mist">{item.text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* Honesty */}
        <section className="border-t border-line py-24 text-center">
          <Reveal>
            <h2 className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
              Straight with you
            </h2>
            <p className="mx-auto mt-8 max-w-2xl font-display text-4xl font-bold leading-tight text-cloud sm:text-5xl">
              We prioritize <span className="text-mint">data dignity</span> over marketing hype.
            </p>
          </Reveal>
          <div className="mx-auto mt-14 grid max-w-3xl gap-10 text-left sm:grid-cols-2">
            <Reveal delay={0.05}>
              <div>
                <h3 className="border-b border-line pb-2 font-mono text-[11px] font-semibold uppercase tracking-label text-cloud">
                  Indicative pricing
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-mist">
                  Fares change constantly. Every price you see is a cached observation with a timestamp —
                  refreshed hourly, never presented as live, never guaranteed. Always confirm the final
                  fare with the airline before you pay.
                </p>
              </div>
            </Reveal>
            <Reveal delay={0.12}>
              <div>
                <h3 className="border-b border-line pb-2 font-mono text-[11px] font-semibold uppercase tracking-label text-cloud">
                  Transparent scores
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-mist">
                  The DealScore compares a fare against the route&apos;s observed price history; the
                  FitScore explains how a trip matches your profile. Both show their work — no black
                  boxes, no fake urgency.
                </p>
              </div>
            </Reveal>
          </div>
        </section>

        {/* Final CTA */}
        <section className="border-t border-line py-24 text-center">
          <Reveal>
            <h2 className="mx-auto max-w-xl font-display text-4xl font-bold text-cloud sm:text-5xl">
              Your next trip is already out there.
            </h2>
            <p className="mx-auto mt-4 max-w-md text-mist">
              Set up your travel profile once — Triplet keeps watching so you don&apos;t have to.
            </p>
            <div className="mt-9 flex justify-center">
              <ButtonLink href="/signup" size="lg">
                Create my travel profile
              </ButtonLink>
            </div>
          </Reveal>
        </section>
      </div>
    </AppShell>
  );
}
