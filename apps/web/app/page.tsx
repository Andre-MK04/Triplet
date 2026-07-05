"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";

import { AppShell } from "../components/AppShell";
import { Hero3D } from "../components/Hero3D";
import { TripCard } from "../components/TripCard";
import { Badge } from "../components/ui/Badge";
import { ButtonLink } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Chip } from "../components/ui/Chip";
import { SectionHeading } from "../components/ui/Misc";
import type { TripOption } from "../lib/types";

const demoSimpleReturn: TripOption = {
  id: "demo-simple",
  tripType: "same_city",
  outboundFlight: {
    id: "demo-out",
    origin: "VIE",
    destination: "ALC",
    departureDateTime: "2026-08-14T07:10:00",
    arrivalDateTime: "2026-08-14T10:05:00",
    airline: "Demo Air",
    price: 39,
    currency: "EUR",
    stops: 0,
    durationMinutes: 175,
    confidenceLevel: "mock",
  },
  returnFlight: {
    id: "demo-ret",
    origin: "ALC",
    destination: "VIE",
    departureDateTime: "2026-08-19T11:30:00",
    arrivalDateTime: "2026-08-19T14:20:00",
    airline: "Demo Air",
    price: 40,
    currency: "EUR",
    stops: 0,
    durationMinutes: 170,
    confidenceLevel: "mock",
  },
  groundTransfer: null,
  totalPrice: 79,
  tripLengthDays: 6,
  nights: 5,
  score: 86,
  explanation:
    "This fare is roughly 45% below the typical price we observe for Vienna–Alicante in August. Direct both ways, sensible departure times, and five full nights of beach weather.",
  warnings: [],
  tags: ["Beach", "Direct", "Cheapest"],
  bookingUrl: null,
  bookingLabel: null,
  provider: "mock",
  linkType: "none",
};

const demoOpenJaw: TripOption = {
  id: "demo-openjaw",
  tripType: "open_jaw",
  outboundFlight: {
    id: "demo-oj-out",
    origin: "VIE",
    destination: "ALC",
    departureDateTime: "2026-09-04T06:40:00",
    arrivalDateTime: "2026-09-04T09:35:00",
    airline: "Demo Air",
    price: 29,
    currency: "EUR",
    stops: 0,
    durationMinutes: 175,
    confidenceLevel: "mock",
  },
  returnFlight: {
    id: "demo-oj-ret",
    origin: "VLC",
    destination: "TRS",
    departureDateTime: "2026-09-10T18:15:00",
    arrivalDateTime: "2026-09-10T20:35:00",
    airline: "Demo Wings",
    price: 35,
    currency: "EUR",
    stops: 0,
    durationMinutes: 140,
    confidenceLevel: "mock",
  },
  groundTransfer: {
    fromAirport: "ALC",
    toAirport: "VLC",
    fromCity: "Alicante",
    toCity: "Valencia",
    durationHours: 2,
    estimatedCost: 18,
    mode: "train/bus",
  },
  totalPrice: 82,
  tripLengthDays: 7,
  nights: 6,
  score: 78,
  explanation:
    "Two Spanish cities for the price of one return. Fly into Alicante, take the coastal train to Valencia, and fly home to Trieste from there.",
  warnings: ["Separate tickets / self-transfer logic. Check final details before booking."],
  tags: ["Two cities", "Food", "Adventure"],
  bookingUrl: null,
  bookingLabel: null,
  provider: "mock",
  linkType: "none",
};

const howItWorks = [
  {
    icon: "📍",
    title: "Pick your airports",
    text: "Choose every airport you're realistically willing to leave from — not just the closest one. More airports, more deals.",
  },
  {
    icon: "🧭",
    title: "Tell Triplet your travel style",
    text: "Beach or city breaks, budget comfort zone, how spontaneous you are, and your comfort rules like “direct only”.",
  },
  {
    icon: "🔔",
    title: "Get alerted when a real deal appears",
    text: "Triplet watches observed fares over time and emails you when something is unusually cheap — as a complete trip idea.",
  },
];

const dealSignals = [
  {
    title: "Deal score",
    text: "A transparent 0–100 score comparing the fare against the route's observed price history — not marketing hype.",
  },
  {
    title: "Fit score",
    text: "How well a trip matches your profile: airports, trip length, style, and comfort rules.",
  },
  {
    title: "Price history",
    text: "Every observed fare is recorded, so “cheap” means cheap versus reality, not versus an inflated anchor price.",
  },
  {
    title: "Honest freshness",
    text: "Every price is labeled live, cached, indicative, or demo — with a “last checked” timestamp. Never guaranteed.",
  },
];

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

export default function LandingPage() {
  return (
    <AppShell>
      {/* Hero */}
      <section className="grid items-center gap-10 pb-20 pt-8 lg:grid-cols-2 lg:pt-16">
        <div className="max-w-xl">
          <Badge tone="mint" className="mb-5">✈ Trip-first flight watching</Badge>
          <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-cloud sm:text-5xl lg:text-6xl">
            Find cheap <span className="text-gradient">trips</span>, not just cheap flights.
          </h1>
          <p className="mt-5 text-lg text-mist">
            Choose your airports, set your travel style, and Triplet watches for unusually cheap fares
            that can become real trips.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <ButtonLink href="/signup" size="lg">Create my travel profile</ButtonLink>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 rounded-full px-6 py-3.5 text-base font-semibold text-mist transition hover:text-cloud"
            >
              See how it works ↓
            </a>
          </div>
          <p className="mt-6 text-xs text-mist/70">
            Prices shown are observed at check time and can change. Triplet never books flights for you.
          </p>
        </div>
        <Reveal delay={0.15}>
          <Hero3D />
        </Reveal>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="scroll-mt-24 py-16">
        <SectionHeading eyebrow="How it works" title="Three steps to smarter trips">
          Triplet turns flight-price noise into complete, explainable trip suggestions.
        </SectionHeading>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {howItWorks.map((step, index) => (
            <Reveal key={step.title} delay={index * 0.12}>
              <Card hover className="h-full">
                <span className="text-3xl" aria-hidden>{step.icon}</span>
                <p className="mt-3 flex items-center gap-2 font-display text-lg font-bold text-cloud">
                  <span className="text-mint">{index + 1}.</span> {step.title}
                </p>
                <p className="mt-2 text-sm text-mist">{step.text}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Example trips */}
      <section className="py-16">
        <SectionHeading eyebrow="Example trips" title="What a Triplet alert looks like">
          These are demo fares from our development dataset — clearly labeled, never presented as live prices.
        </SectionHeading>
        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <Reveal><TripCard trip={demoSimpleReturn} isDemo /></Reveal>
          <Reveal delay={0.12}><TripCard trip={demoOpenJaw} isDemo /></Reveal>
        </div>
      </section>

      {/* Travel profile preview */}
      <section className="py-16">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <SectionHeading eyebrow="Your travel profile" title="Deals that actually fit you" />
            <p className="mx-auto mt-3 max-w-xl text-center text-mist lg:text-left">
              A two-minute quiz teaches Triplet which airports work for you, how long you like to travel,
              and what a “good deal” means in your budget.
            </p>
          </div>
          <Reveal>
            <Card className="space-y-5">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-mist">Your airports</p>
                <div className="flex flex-wrap gap-2">
                  {["Vienna VIE", "Zagreb ZAG", "Trieste TRS", "Venice VCE", "Budapest BUD"].map(
                    (airport, index) => (
                      <Chip key={airport} selected={index < 3}>{airport}</Chip>
                    ),
                  )}
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-mist">
                  <span>Budget comfort zone</span>
                  <span className="text-mint">under €200</span>
                </div>
                <input type="range" readOnly value={40} min={0} max={100} className="w-full" aria-label="Budget preference preview" />
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-mist">
                  <span>Trip length</span>
                  <span className="text-mint">4–8 days</span>
                </div>
                <input type="range" readOnly value={55} min={0} max={100} className="w-full" aria-label="Trip length preference preview" />
              </div>
              <div className="flex flex-wrap gap-2">
                {["🏖 Beach", "🍜 Food", "🎭 Culture", "⛰ Nature"].map((style, index) => (
                  <Chip key={style} selected={index < 2}>{style}</Chip>
                ))}
              </div>
            </Card>
          </Reveal>
        </div>
      </section>

      {/* Deal intelligence */}
      <section className="py-16">
        <SectionHeading eyebrow="Deal intelligence" title="“Cheap” is measured, not claimed">
          Every suggestion explains itself: what it costs, why it's unusual, and what to watch out for.
        </SectionHeading>
        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {dealSignals.map((signal, index) => (
            <Reveal key={signal.title} delay={index * 0.08}>
              <Card hover className="h-full">
                <h3 className="font-display text-base font-bold text-mint">{signal.title}</h3>
                <p className="mt-2 text-sm text-mist">{signal.text}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Security */}
      <section className="py-16">
        <Reveal>
          <Card className="mx-auto max-w-3xl text-center">
            <span className="text-3xl" aria-hidden>🔒</span>
            <h2 className="mt-3 font-display text-2xl font-bold text-cloud">Your data, guarded like a passport</h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-mist">
              Passwords are hashed, sessions live in httpOnly cookies, and your profile is only used to rank
              trips for you. We don't sell your data, and unsubscribing works with one click on every email.
            </p>
            <Link href="/security" className="mt-4 inline-block text-sm font-semibold text-sky hover:text-cloud">
              Read the security &amp; privacy overview →
            </Link>
          </Card>
        </Reveal>
      </section>

      {/* Pricing teaser */}
      <section className="py-16">
        <SectionHeading eyebrow="Pricing" title="Free to watch, Pro to hunt harder" />
        <div className="mx-auto mt-10 grid max-w-3xl gap-4 sm:grid-cols-2">
          <Reveal>
            <Card hover className="h-full">
              <h3 className="font-display text-lg font-bold text-cloud">Free</h3>
              <p className="mt-1 text-3xl font-bold text-mint">€0</p>
              <ul className="mt-4 space-y-2 text-sm text-mist">
                <li>3 saved watches</li>
                <li>Daily checks</li>
                <li>Up to 6 origin airports</li>
              </ul>
            </Card>
          </Reveal>
          <Reveal delay={0.1}>
            <Card hover className="h-full border-mint/30">
              <h3 className="font-display text-lg font-bold text-cloud">Pro</h3>
              <p className="mt-1 text-3xl font-bold text-mint">soon</p>
              <ul className="mt-4 space-y-2 text-sm text-mist">
                <li>30 watches &amp; more airports</li>
                <li>Priority + urgent deal alerts</li>
                <li>Advanced open-jaw trips</li>
              </ul>
            </Card>
          </Reveal>
        </div>
        <p className="mt-6 text-center">
          <Link href="/pricing" className="text-sm font-semibold text-sky hover:text-cloud">
            Compare plans →
          </Link>
        </p>
      </section>

      {/* Final CTA */}
      <section className="py-20">
        <Reveal>
          <div className="glass rounded-card relative overflow-hidden px-6 py-14 text-center">
            <div aria-hidden className="absolute inset-x-0 -top-32 mx-auto h-64 w-64 rounded-full bg-mint/10 blur-3xl" />
            <h2 className="font-display text-3xl font-bold text-cloud sm:text-4xl">
              Your next trip is already out there.
            </h2>
            <p className="mx-auto mt-3 max-w-md text-mist">
              Set up your travel profile once — Triplet keeps watching so you don't have to.
            </p>
            <div className="mt-7">
              <ButtonLink href="/signup" size="lg">Create my travel profile</ButtonLink>
            </div>
          </div>
        </Reveal>
      </section>
    </AppShell>
  );
}
