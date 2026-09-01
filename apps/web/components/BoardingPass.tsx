"use client";

import { rememberFareCheck } from "../lib/fareCheck";
import { formatPrice } from "../lib/format";
import { CHECK_PRICE_LABEL, pricePresentation } from "../lib/price";
import type { Flight, GroundTransfer, TripOption } from "../lib/types";

function legTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function legDate(iso: string): string {
  return new Date(iso)
    .toLocaleDateString("en-GB", { month: "short", day: "2-digit", weekday: "short" })
    .toUpperCase();
}

function durationLabel(flight: Flight): string {
  const parts: string[] = [];
  if (flight.durationMinutes) {
    const hours = Math.floor(flight.durationMinutes / 60);
    const minutes = flight.durationMinutes % 60;
    parts.push(`${hours}H${minutes ? ` ${minutes}M` : ""}`);
  }
  if (flight.stops != null) parts.push(flight.stops === 0 ? "DIRECT" : `${flight.stops} STOP${flight.stops > 1 ? "S" : ""}`);
  return parts.join(" · ") || "SCHEDULE VARIES";
}

function Leg({ label, flight }: { label: string; flight: Flight }) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 py-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.2fr)]">
      <div>
        <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
          {label} · {flight.origin}
        </span>
        <span className="mono-num font-display text-4xl font-bold text-cloud sm:text-5xl">
          {legTime(flight.departureDateTime)}
        </span>
      </div>
      <div className="text-center">
        <span className="block font-mono text-[9px] uppercase tracking-label text-mist">{durationLabel(flight)}</span>
        <span aria-hidden className="mx-auto my-1.5 block h-px w-full max-w-32 bg-line" />
        <span aria-hidden className="font-mono text-xs text-mint">→</span>
      </div>
      <div className="text-right sm:text-left">
        <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
          {flight.destination}
        </span>
        <span className="mono-num font-display text-4xl font-bold text-cloud sm:text-5xl">
          {legTime(flight.arrivalDateTime)}
        </span>
      </div>
      <div className="col-span-3 sm:col-span-1 sm:text-right">
        <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-cloud">
          {legDate(flight.departureDateTime)}
        </span>
        <span className="mt-1 block font-mono text-xs text-mist">{flight.airline || "Airline TBC"}</span>
      </div>
    </div>
  );
}

/** A ground crossing the traveller arranges themselves. Never in the total. */
function GroundHop({ transfer }: { transfer: GroundTransfer }) {
  return (
    <p className="py-3 font-mono text-xs text-gold">
      <span className="text-mist/70">VIA</span> {transfer.fromCity} → {transfer.toCity} · ~
      {transfer.durationHours}h by {transfer.mode} · ~{formatPrice(transfer.estimatedCost)} estimate
      <span className="text-mist/70"> · not included in the fare</span>
    </p>
  );
}

/**
 * The legs to print, in order.
 *
 * A multi-city chain carries its own segment list; a plain return does not, so
 * one is synthesised from the outbound/return pair. Rendering from a list either
 * way means a four-flight itinerary prints four flights rather than collapsing
 * to its first and last, which is what the fixed out/return layout did.
 */
type RenderedLeg =
  | { key: string; label: string; flight: Flight; bookingUrl?: string | null }
  | { key: string; ground: GroundTransfer };

function legsToRender(trip: TripOption): RenderedLeg[] {
  const segments = trip.segments ?? [];
  if (segments.length > 0) {
    const flights = segments.filter((s) => s.kind === "flight");
    return segments.flatMap<RenderedLeg>((segment, index) => {
      if (segment.kind === "ground") {
        return segment.transfer ? [{ key: `g${index}`, ground: segment.transfer }] : [];
      }
      if (!segment.flight) return [];
      const flightIndex = flights.indexOf(segment);
      return [
        {
          key: `f${index}`,
          label: `Leg ${flightIndex + 1}`,
          flight: segment.flight,
          bookingUrl: segment.bookingUrl,
        },
      ];
    });
  }

  const fallback: RenderedLeg[] = [
    { key: "out", label: "Out", flight: trip.outboundFlight },
    ...(trip.groundTransfer ? [{ key: "via", ground: trip.groundTransfer } as RenderedLeg] : []),
    { key: "ret", label: "Ret", flight: trip.returnFlight },
  ];
  return fallback;
}

export function BoardingPass({ trip }: { trip: TripOption }) {
  const bookingHref = trip.bookingUrl ?? trip.affiliateUrl ?? trip.providerDeepLink ?? null;
  const legs = legsToRender(trip);
  // Legs bought separately are separate contracts, and the page must not imply
  // otherwise: a missed connection between them is not protected.
  const separateTickets = legs.filter((leg) => "flight" in leg && leg.bookingUrl).length > 1;

  return (
    <section className="border border-line bg-ink-raised">
      <div className="grid lg:grid-cols-[minmax(0,8fr)_minmax(0,3fr)]">
        <div className="px-6">
          {legs.map((leg, index) => (
            <div key={leg.key}>
              {index > 0 ? (
                /* Perforation between segments, boarding-pass style. */
                <div className="border-t border-dashed border-line" aria-hidden />
              ) : null}
              {"ground" in leg ? (
                <GroundHop transfer={leg.ground} />
              ) : (
                <>
                  <Leg label={leg.label} flight={leg.flight} />
                  {leg.bookingUrl ? (
                    <a
                      href={leg.bookingUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mb-4 inline-block font-mono text-[11px] font-semibold uppercase tracking-label text-mist underline transition-colors hover:text-mint"
                    >
                      {CHECK_PRICE_LABEL} for this leg ↗
                    </a>
                  ) : null}
                </>
              )}
            </div>
          ))}
        </div>

        <div className="border-t border-line px-6 py-6 lg:border-l lg:border-t-0">
          <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Total fare
          </span>
          <span className="mono-num mt-2 block font-display text-4xl font-bold leading-tight text-coral">
            {pricePresentation(trip).primary}
          </span>
          <p className="mt-3 font-mono text-[10px] uppercase leading-relaxed tracking-label text-mist">
            {pricePresentation(trip).secondary || "Recently observed fare · verify before booking"}
          </p>
          {separateTickets ? (
            <p className="mt-3 border-l-2 border-gold/40 pl-3 font-mono text-[10px] uppercase leading-relaxed tracking-label text-gold">
              Separate tickets — each leg is booked on its own. A delay on one does not protect
              the next.
            </p>
          ) : null}
          {bookingHref ? (
            <a
              href={bookingHref}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => rememberFareCheck(trip)}
              className="mt-6 block bg-mint px-6 py-3.5 text-center font-mono text-[11px] font-semibold uppercase tracking-label text-mint-ink transition-opacity hover:opacity-90"
            >
              {CHECK_PRICE_LABEL} ↗
            </a>
          ) : (
            <p className="mt-6 border border-line px-4 py-3 text-center font-mono text-[10px] uppercase tracking-label text-mist/70">
              No booking link — search the route with the airline
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
