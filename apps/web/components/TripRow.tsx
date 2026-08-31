"use client";

import Link from "next/link";
import { useState } from "react";

import { AIRPORTS_BY_CODE } from "../lib/airports";
import { formatPrice, timeAgo } from "../lib/format";
import type { Flight, TripOption } from "../lib/types";
import { ScoreDial } from "./ScoreDial";

function cityFor(code: string): string {
  return AIRPORTS_BY_CODE[code]?.city ?? code;
}

function countryFor(code: string): string | null {
  return AIRPORTS_BY_CODE[code]?.country ?? null;
}

function legDate(iso: string): string {
  return new Date(iso)
    .toLocaleDateString("en-GB", { day: "2-digit", month: "short" })
    .toUpperCase();
}

function legTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function telemetry(flight: Flight): string {
  const stops =
    flight.stops == null ? "STOPS N/A" : flight.stops === 0 ? "DIRECT" : `${flight.stops} STOP${flight.stops > 1 ? "S" : ""}`;
  return flight.airline ? `${stops} · ${flight.airline}` : stops;
}

const STALE_AFTER_DAYS = 3;

/** The oldest fare in the trip — a total is only as fresh as its stalest leg. */
function oldestSeenAt(trip: TripOption): string | null {
  const flights = (trip.segments ?? [])
    .filter((segment) => segment.kind === "flight" && segment.flight)
    .map((segment) => segment.flight!);
  const seen = (flights.length > 0 ? flights : [trip.outboundFlight])
    .map((flight) => flight.observedAt)
    .filter((value): value is string => Boolean(value));
  if (seen.length === 0) return null;
  return seen.reduce((oldest, value) => (new Date(value) < new Date(oldest) ? value : oldest));
}

function fareAgeDays(trip: TripOption): number | null {
  const seen = oldestSeenAt(trip);
  if (!seen) return null;
  const days = (Date.now() - new Date(seen).getTime()) / 86_400_000;
  return Math.max(0, Math.floor(days));
}

function freshness(trip: TripOption): string {
  // The day the provider last saw the fare, not when we fetched it — their data
  // is a cache of what travellers recently searched, so a price can legitimately
  // be several days old however often we refresh.
  const seen = oldestSeenAt(trip);
  const ago = seen ? timeAgo(seen) : null;
  const multiLeg = (trip.segments ?? []).filter((s) => s.kind === "flight").length > 2;
  if (!ago) return "price age unknown";
  return multiLeg ? `oldest price seen ${ago}` : `price seen ${ago}`;
}

function LegLine({ label, flight, showPrice }: { label: string; flight: Flight; showPrice: boolean }) {
  return (
    <p className="mono-num font-mono text-xs text-cloud">
      <span className="text-mist/70">{label}</span> {flight.origin} → {flight.destination} ·{" "}
      {legDate(flight.departureDateTime)} {legTime(flight.departureDateTime)} · {telemetry(flight)}
      {/* Bundled round trips have one real total; per-leg prices would be misleading. */}
      {showPrice ? ` · ${formatPrice(flight.price, flight.currency)}` : ""}
    </p>
  );
}

export function TripRow({ trip, onSaveAlert }: { trip: TripOption; onSaveAlert?: () => void }) {
  const [open, setOpen] = useState(false);

  const dest = trip.outboundFlight.destination;
  const stays = trip.stays ?? [];
  const isChained = stays.length > 1;
  const destinationCity = trip.destination?.city ?? cityFor(dest);
  const destinationCountry = trip.destination?.country ?? countryFor(dest);
  const overBudget = trip.tags.some((tag) => tag.toLowerCase() === "over budget");
  const isOpenJaw = trip.tripType === "open_jaw";
  const returnFrom = trip.returnFlight.origin;
  const dealValue = trip.dealScore ?? trip.score;
  const bookingHref = trip.bookingUrl ?? trip.affiliateUrl ?? trip.providerDeepLink ?? null;
  const ageDays = fareAgeDays(trip);
  const staleFare = ageDays != null && ageDays > STALE_AFTER_DAYS;

  return (
    <div className="border-b border-line">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="grid w-full grid-cols-2 items-center gap-x-4 gap-y-3 py-5 text-left transition-colors hover:bg-mint/5 sm:grid-cols-[minmax(0,3fr)_minmax(0,3fr)_minmax(0,2fr)_minmax(0,2fr)_minmax(0,2fr)_min-content]"
      >
        <span>
          <span className="block font-display text-xl font-bold uppercase leading-tight text-cloud">
            {isChained ? (
              stays.map((stay, index) => (
                <span key={`${stay.code}-${index}`}>
                  {index > 0 ? <span className="text-mist"> · </span> : null}
                  {stay.city}
                </span>
              ))
            ) : (
              <>
                {destinationCity}
                {isOpenJaw ? <span className="text-mist"> ⇢ {cityFor(returnFrom)}</span> : null}
              </>
            )}
          </span>
          <span className="mt-1 block font-mono text-xs uppercase text-mist">
            {isChained
              ? stays.map((stay) => `${stay.nights}n ${stay.code}`).join(" · ")
              : `${destinationCountry ? `${destinationCountry} · ` : ""}${
                  trip.destination?.continent ? `${trip.destination.continent} · ` : ""
                }${dest}${isOpenJaw ? ` → ${returnFrom}` : ""}`}
          </span>
        </span>

        <span className="text-right sm:text-left">
          <span className="mono-num block font-mono text-sm text-cloud">
            {legDate(trip.outboundFlight.departureDateTime)} — {legDate(trip.returnFlight.departureDateTime)}
          </span>
          <span className="mt-1 block font-mono text-[10px] uppercase tracking-label text-mist/70">
            {trip.nights} nights
            {isChained ? ` · ${stays.length} cities` : isOpenJaw ? " · two cities" : ""}
          </span>
        </span>

        <span className="hidden font-mono text-xs text-cloud sm:block">{telemetry(trip.outboundFlight)}</span>

        <span className="flex gap-3">
          <ScoreDial value={dealValue} tone="gold" size={44} label="Deal" />
          {trip.fitScore != null ? <ScoreDial value={trip.fitScore} tone="mint" size={44} label="Fit" /> : null}
        </span>

        <span className="text-right">
          {overBudget ? (
            <span className="mb-1 inline-block border border-coral/40 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-label text-coral">
              Over budget
            </span>
          ) : null}
          <span
            className={
              "mono-num block font-display text-3xl font-bold leading-none " +
              (overBudget ? "text-mist/60" : "text-coral")
            }
          >
            {formatPrice(trip.totalPrice)}
          </span>
          <span
            className={
              "mt-1 block font-mono text-[10px] uppercase tracking-label " +
              (staleFare ? "text-gold" : "text-mist/70")
            }
          >
            {freshness(trip)}
          </span>
        </span>

        <span
          aria-hidden
          className={"hidden text-mist transition-transform sm:block " + (open ? "rotate-90" : "")}
        >
          ›
        </span>
      </button>

      {open ? (
        <div className="mb-5 border-l-2 border-mint/40 bg-ink-raised px-5 py-4">
          {trip.segments && trip.segments.length > 0 ? (
            <ol className="space-y-1.5">
              {trip.segments.map((segment, index) => (
                <li key={`${segment.origin}-${segment.destination}-${index}`}>
                  {segment.kind === "flight" && segment.flight ? (
                    <span className="flex flex-wrap items-baseline gap-x-3">
                      <LegLine
                        label={`${index + 1}`}
                        flight={segment.flight}
                        showPrice={trip.fareKind !== "round_trip_bundle"}
                      />
                      {segment.bookingUrl ? (
                        <a
                          href={segment.bookingUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(event) => event.stopPropagation()}
                          className="font-mono text-[10px] uppercase tracking-label text-mint transition-colors hover:text-cloud"
                        >
                          Check ↗
                        </a>
                      ) : null}
                    </span>
                  ) : segment.transfer ? (
                    <p className="font-mono text-xs text-mist">
                      <span className="text-mist/70">{index + 1}</span> {segment.originCity} ⇢{" "}
                      {segment.destinationCity} · overland ~{segment.transfer.durationHours}h · ~
                      {formatPrice(segment.transfer.estimatedCost)} est.
                      <span className="text-mist/60"> · not in the price</span>
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : (
          <div className="space-y-1.5">
            <LegLine label="OUT" flight={trip.outboundFlight} showPrice={trip.fareKind !== "round_trip_bundle"} />
            {trip.groundTransfer ? (
              <p className="font-mono text-xs text-mist">
                <span className="text-mist/70">VIA</span> {trip.groundTransfer.fromCity} →{" "}
                {trip.groundTransfer.toCity} · ~{trip.groundTransfer.durationHours}h{" "}
                {trip.groundTransfer.mode}
                {trip.groundTransfer.estimatedCost != null
                  ? ` · ~${formatPrice(trip.groundTransfer.estimatedCost)} est.`
                  : ""}
              </p>
            ) : null}
            <LegLine label="RET" flight={trip.returnFlight} showPrice={trip.fareKind !== "round_trip_bundle"} />
          </div>
          )}

          {trip.groundEstimate ? (
            <p className="mt-3 font-mono text-xs text-mist">
              Flights {formatPrice(trip.flightCost ?? trip.totalPrice)} · overland roughly{" "}
              {formatPrice(trip.groundEstimate)} on top, arranged by you.
            </p>
          ) : null}

          {staleFare ? (
            <p className="mt-4 max-w-2xl font-mono text-xs text-gold">
              This price was last seen {ageDays} days ago. Aviasales prices what is on sale right now,
              so check before you count on it.
            </p>
          ) : null}

          {trip.explanation ? <p className="mt-4 max-w-2xl text-sm leading-relaxed text-mist">{trip.explanation}</p> : null}

          {trip.warnings.length > 0 ? (
            <ul className="mt-3 space-y-1">
              {trip.warnings.map((warning) => (
                <li key={warning} className="font-mono text-xs text-gold">
                  {warning}
                </li>
              ))}
            </ul>
          ) : null}

          <div className="mt-5 flex flex-wrap items-center gap-5">
            {bookingHref ? (
              <a
                href={bookingHref}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint transition-colors hover:text-cloud"
              >
                {trip.bookingLabel ?? "Check price"} ↗
              </a>
            ) : (
              <span className="font-mono text-[11px] uppercase tracking-label text-mist/60">
                No booking link for this fare
              </span>
            )}
            {trip.suggestionId ? (
              <Link
                href={`/trip/${trip.suggestionId}`}
                className="font-mono text-[11px] font-semibold uppercase tracking-label text-cloud transition-colors hover:text-mint"
              >
                Full trip page →
              </Link>
            ) : null}
            {onSaveAlert ? (
              <button
                type="button"
                onClick={onSaveAlert}
                className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist transition-colors hover:text-mint"
              >
                Watch this search
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
