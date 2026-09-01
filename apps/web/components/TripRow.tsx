"use client";

import Link from "next/link";
import { useState } from "react";

import { AIRPORTS_BY_CODE } from "../lib/airports";
import { formatPrice } from "../lib/format";
import { rememberFareCheck } from "../lib/fareCheck";
import { CHECK_PRICE_LABEL, priceBadge, pricePresentation } from "../lib/price";
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
  const price = pricePresentation(trip);
  const badge = priceBadge(trip);

  const routeLabel = isChained
    ? stays.map((stay) => stay.city).join(" to ")
    : `${cityFor(trip.outboundFlight.origin)} to ${destinationCity}`;

  return (
    <div className="border-b border-line">
      {/* Expanding and checking the live price are two different actions, so
          they are two sibling controls. They used to be one: the whole row was
          a button and the only live-price link lived inside the panel it
          opened, which put the main conversion action behind a disclosure and
          would have meant nesting an anchor inside a button to fix naively. */}
      {/* Stacked on a phone, side by side from small up. Beside the row, the
          link is shrink-0 and takes its natural width, which on a 375px screen
          left about 110px per grid column — narrow enough that a price badge
          or a long city name spilled into its neighbour. */}
      <div className="flex flex-col items-stretch gap-2 sm:flex-row">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          className="grid min-w-0 flex-1 grid-cols-2 items-center gap-x-4 gap-y-3 py-5 text-left transition-colors hover:bg-mint/5 sm:grid-cols-[minmax(0,3fr)_minmax(0,3fr)_minmax(0,2fr)_minmax(0,2fr)_minmax(0,2fr)_min-content]"
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
          {badge ? (
            <span className="mt-1.5 inline-flex items-center gap-1 border border-mint/40 px-1.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
              {badge.label}
            </span>
          ) : null}
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
          <span className="mt-1 block font-mono text-[11px] uppercase tracking-label text-mist/70">
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
            <span className="mb-1 inline-block border border-coral/40 px-1.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-label text-coral">
              Over budget
            </span>
          ) : null}
          <span
            className={
              "mono-num block font-display leading-none " +
              (overBudget ? "text-mist/60" : "text-coral")
            }
          >
            <span className="mr-1 align-middle text-xs font-normal uppercase tracking-label text-mist">
              {price.isEstimate ? "Est. from" : price.confidence === "aging" || price.isStale ? "Recently from" : "from"}
            </span>
            <span className="align-middle text-3xl font-bold">
              {formatPrice(price.isEstimate || !trip.price ? trip.totalPrice : trip.price.amount)}
            </span>
          </span>
          {price.secondary ? (
            <span
              className={
                // How old the fare is decides how much of the price to
                // believe, so it is read at the same size as the labels around
                // it rather than shrunk into decoration.
                "mt-1 block font-mono text-[11px] uppercase tracking-label " +
                (price.isStale || price.confidence === "aging" ? "text-gold" : "text-mist/70")
              }
            >
              {price.secondary}
            </span>
          ) : null}
        </span>

          <span
            aria-hidden
            className={"text-mist transition-transform " + (open ? "rotate-90" : "")}
          >
            ›
          </span>
        </button>

        {bookingHref ? (
          <a
            href={bookingHref}
            target="_blank"
            rel="noopener noreferrer"
            // Note the check locally so Triplet can later ask how the price
            // held up. Nothing is sent now — following a link is not consent
            // to be measured.
            onClick={() => rememberFareCheck(trip)}
            // Named for this specific trip so a screen reader hears which row
            // it belongs to rather than a wall of identical links.
            aria-label={`${CHECK_PRICE_LABEL} for ${routeLabel}`}
            className="mb-4 flex shrink-0 items-center justify-center border border-mint/30 px-3 py-2.5 text-center font-mono text-[11px] font-semibold uppercase leading-tight tracking-label text-mint transition-colors hover:bg-mint hover:text-mint-ink sm:my-2 sm:mb-2 sm:border-0 sm:px-4 sm:py-0"
          >
            {CHECK_PRICE_LABEL} ↗
          </a>
        ) : null}
      </div>

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
                          className="font-mono text-[11px] uppercase tracking-label text-mint transition-colors hover:text-cloud"
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

          {badge ? (
            <p className="mb-3 max-w-2xl font-mono text-xs text-mint">{badge.explanation}</p>
          ) : null}
          {price.isStale ? (
            <p className="mt-4 max-w-2xl font-mono text-xs text-gold">
              This fare was last seen more than two days ago. Aviasales prices what is on sale right
              now, so treat this as a lead rather than a quote.
            </p>
          ) : null}
          {price.isEstimate ? (
            <p className="mt-4 max-w-2xl font-mono text-xs text-mist">
              Each flight was priced separately and added up — nobody observed this itinerary as a
              single fare, and booking it as one usually costs more.
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
                {CHECK_PRICE_LABEL} ↗
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
