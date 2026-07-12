import { formatPrice } from "../lib/format";
import type { Flight, TripOption } from "../lib/types";

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

export function BoardingPass({ trip }: { trip: TripOption }) {
  const bookingHref = trip.bookingUrl ?? trip.affiliateUrl ?? trip.providerDeepLink ?? null;

  return (
    <section className="border border-line bg-ink-raised">
      <div className="grid lg:grid-cols-[minmax(0,8fr)_minmax(0,3fr)]">
        <div className="px-6">
          <Leg label="Out" flight={trip.outboundFlight} />
          {/* Perforation between segments, boarding-pass style. */}
          <div className="border-t border-dashed border-line" aria-hidden />
          {trip.groundTransfer ? (
            <>
              <p className="py-3 font-mono text-xs text-gold">
                <span className="text-mist/70">VIA</span> {trip.groundTransfer.fromCity} →{" "}
                {trip.groundTransfer.toCity} · ~{trip.groundTransfer.durationHours}h by{" "}
                {trip.groundTransfer.mode} · ~{formatPrice(trip.groundTransfer.estimatedCost)} estimate
              </p>
              <div className="border-t border-dashed border-line" aria-hidden />
            </>
          ) : null}
          <Leg label="Ret" flight={trip.returnFlight} />
        </div>

        <div className="border-t border-line px-6 py-6 lg:border-l lg:border-t-0">
          <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Total fare
          </span>
          <span className="mono-num mt-2 block font-display text-5xl font-bold leading-none text-coral">
            {formatPrice(trip.totalPrice, trip.outboundFlight.currency)}
          </span>
          <p className="mt-3 font-mono text-[10px] uppercase leading-relaxed tracking-label text-mist">
            Indicative price · verify before booking
          </p>
          {bookingHref ? (
            <a
              href={bookingHref}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 block bg-mint px-6 py-3.5 text-center font-mono text-[11px] font-semibold uppercase tracking-label text-mint-ink transition-opacity hover:opacity-90"
            >
              {trip.bookingLabel ?? "Check price"} ↗
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
