"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useState } from "react";

import { airportCity } from "../lib/airports";
import { confidenceLabel, formatDate, formatDuration, formatPrice, formatTime, timeAgo } from "../lib/format";
import type { Flight, ScoreComponent, TripOption } from "../lib/types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";

export function DealScoreBadge({ score }: { score: number }) {
  const tone = score >= 75 ? "mint" : score >= 50 ? "gold" : "neutral";
  return (
    <Badge tone={tone} title="Explainable deal score from 0 to 100: price vs. observed history and trip quality" className="font-bold">
      {score} deal score
    </Badge>
  );
}

export function FitScoreBadge({ score }: { score: number }) {
  const tone = score >= 75 ? "sky" : score >= 50 ? "neutral" : "coral";
  return (
    <Badge tone={tone} title="How well this trip matches your travel profile" className="font-bold">
      {score} fit
    </Badge>
  );
}

function ScoreBreakdown({ title, components }: { title: string; components: ScoreComponent[] }) {
  if (components.length === 0) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-mist/70">{title}</p>
      <ul className="mt-1 space-y-0.5">
        {components.map((component) => (
          <li key={component.label} className="flex items-baseline justify-between gap-3 text-xs">
            <span className="text-mist">{component.label}</span>
            <span className={component.points > 0 ? "font-semibold text-mint" : "font-semibold text-coral"}>
              {component.points > 0 ? `+${component.points}` : component.points}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FlightRow({ label, flight }: { label: string; flight: Flight }) {
  const duration = formatDuration(flight.durationMinutes);
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-ink-soft/60 px-3.5 py-2.5">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-mist/70">{label}</p>
        <p className="truncate text-sm font-semibold text-cloud">
          {airportCity(flight.origin)} <span className="text-mist">{flight.origin}</span>
          <span aria-hidden className="mx-1.5 text-mint">→</span>
          {airportCity(flight.destination)} <span className="text-mist">{flight.destination}</span>
        </p>
        <p className="text-xs text-mist">
          {formatDate(flight.departureDateTime)} · {formatTime(flight.departureDateTime)}–{formatTime(flight.arrivalDateTime)}
          {duration ? ` · ${duration}` : ""}
          {typeof flight.stops === "number" ? ` · ${flight.stops === 0 ? "direct" : `${flight.stops} stop${flight.stops > 1 ? "s" : ""}`}` : ""}
        </p>
        <p className="truncate text-xs text-mist/70">{flight.airline}</p>
      </div>
      <p className="shrink-0 text-sm font-bold text-cloud">{formatPrice(flight.price, flight.currency)}</p>
    </div>
  );
}

type TripCardProps = {
  trip: TripOption;
  onSaveAlert?: () => void;
  isDemo?: boolean;
};

export function TripCard({ trip, onSaveAlert, isDemo = false }: TripCardProps) {
  const [expanded, setExpanded] = useState(false);
  const reducedMotion = useReducedMotion();
  const outbound = trip.outboundFlight;
  const inbound = trip.returnFlight;
  const confidence = confidenceLabel(isDemo ? "mock" : outbound.confidenceLevel);
  const observed = timeAgo(outbound.observedAt);
  const routeTitle =
    trip.tripType === "open_jaw"
      ? `${airportCity(outbound.origin)} → ${airportCity(outbound.destination)} / ${airportCity(inbound.origin)} → ${airportCity(inbound.destination)}`
      : `${airportCity(outbound.origin)} → ${airportCity(outbound.destination)}`;

  return (
    <motion.article
      layout={!reducedMotion}
      whileHover={reducedMotion ? undefined : { y: -4 }}
      className="glass rounded-card relative flex flex-col gap-3.5 p-5 shadow-deal"
    >
      {/* Boarding-pass notches */}
      <span aria-hidden className="absolute -left-2 top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-ink" />
      <span aria-hidden className="absolute -right-2 top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-ink" />

      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-display text-lg font-bold text-cloud">{routeTitle}</h3>
          <p className="text-xs text-mist">
            {formatDate(outbound.departureDateTime)} – {formatDate(inbound.departureDateTime)} · {trip.nights}{" "}
            {trip.nights === 1 ? "night" : "nights"}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-display text-2xl font-bold text-mint">{formatPrice(trip.totalPrice, outbound.currency)}</p>
          <p className="text-[11px] text-mist/70">total, flights{trip.groundTransfer ? " + transfer" : ""}</p>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-1.5">
        <DealScoreBadge score={trip.dealScore ?? trip.score} />
        {typeof trip.fitScore === "number" ? <FitScoreBadge score={trip.fitScore} /> : null}
        <Badge tone={confidence.tone}>{confidence.label}</Badge>
        {trip.tripType === "open_jaw" ? <Badge tone="sky">Open-jaw</Badge> : null}
        {trip.tags.slice(0, 3).map((tag) => (
          <Badge key={tag}>{tag}</Badge>
        ))}
      </div>

      <div className="space-y-2">
        <FlightRow label="Outbound" flight={outbound} />
        {trip.groundTransfer ? (
          <p className="flex items-center gap-2 px-2 text-xs text-gold">
            <span aria-hidden>🚆</span>
            {trip.groundTransfer.fromCity} → {trip.groundTransfer.toCity}, approx.{" "}
            {trip.groundTransfer.durationHours}h by {trip.groundTransfer.mode} (~
            {formatPrice(trip.groundTransfer.estimatedCost)})
          </p>
        ) : null}
        <FlightRow label="Return" flight={inbound} />
      </div>

      {expanded ? (
        <div className="space-y-2 rounded-xl border border-line bg-ink-soft/40 p-3.5 text-sm text-mist">
          <p className="text-cloud">{trip.explanation}</p>
          {trip.warnings.length > 0 ? (
            <ul className="space-y-1">
              {trip.warnings.map((warning) => (
                <li key={warning} className="flex gap-2 text-xs text-gold">
                  <span aria-hidden>⚠️</span>
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}
          {trip.tripType === "open_jaw" ? (
            <p className="text-xs text-gold">
              Separate tickets / self-transfer logic. Check final details before booking.
            </p>
          ) : null}
          {(trip.dealScoreBreakdown?.length || trip.fitScoreBreakdown?.length) ? (
            <div className="grid gap-3 border-t border-line pt-3 sm:grid-cols-2">
              <ScoreBreakdown title="Deal score factors" components={trip.dealScoreBreakdown ?? []} />
              <ScoreBreakdown title="Fit score factors" components={trip.fitScoreBreakdown ?? []} />
            </div>
          ) : null}
          <p className="text-xs text-mist/70">
            {observed ? `Last checked ${observed}. ` : ""}Prices are observed, not guaranteed — check the final
            price with the provider.
          </p>
        </div>
      ) : null}

      <footer className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-dashed border-line pt-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="text-sm font-medium text-sky transition hover:text-cloud"
            aria-expanded={expanded}
          >
            {expanded ? "Hide details" : "Why this works"}
          </button>
          {trip.suggestionId ? (
            <Link
              href={`/trip/${trip.suggestionId}`}
              className="text-sm font-medium text-mist transition hover:text-cloud"
            >
              Open →
            </Link>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {onSaveAlert ? (
            <Button variant="secondary" size="sm" onClick={onSaveAlert}>
              Save alert
            </Button>
          ) : null}
          {trip.bookingUrl ? (
            <a
              href={trip.bookingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-mint px-4 py-2 text-sm font-semibold text-ink transition hover:brightness-110"
            >
              {trip.bookingLabel || "Check price"} ↗
            </a>
          ) : (
            <span className="text-xs text-mist/70">No booking link for demo fares</span>
          )}
        </div>
      </footer>
    </motion.article>
  );
}
