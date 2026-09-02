import { airportCity } from "./airports";
import type { TripOption } from "./types";

/**
 * What a shared trip link should say when it unfurls in a chat app.
 *
 * These URLs travel by message far more than by search, so the preview is
 * often the only thing a recipient sees before deciding whether to open it.
 * "A trip on Triplet" told them nothing.
 *
 * The wording is bound by the same rule as everything else that shows a price:
 * an observed fare is not a bookable one. A preview may say `from €421`; it may
 * never say `Book for €421` or `Live €421`, because by the time someone reads
 * a forwarded message the fare may be hours old and gone.
 */

/** Kept short enough that no platform truncates the interesting half. */
const MAX_TITLE = 70;

function city(code: string | undefined | null): string {
  if (!code) return "";
  return airportCity(code) || code;
}

function money(amount: number, currency: string): string {
  const symbol = currency === "EUR" ? "€" : currency === "GBP" ? "£" : currency === "USD" ? "$" : "";
  const rounded = Math.round(amount);
  return symbol ? `${symbol}${rounded}` : `${rounded} ${currency}`;
}

function shortDate(iso: string | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

/**
 * The route, as a chain of cities.
 *
 * Multi-city trips read as the chain they are rather than collapsing to
 * first-and-last, because "Vienna → Istanbul" would misdescribe a trip through
 * Rome and Athens as a direct one.
 */
export function tripRouteLabel(trip: TripOption): string {
  const segments = trip.segments ?? [];

  if (trip.tripType === "multi_city" && segments.length > 0) {
    const first = segments[0];
    const stops = [first?.originCity || city(first?.origin)];
    for (const segment of segments) {
      const next = segment.destinationCity || city(segment.destination);
      if (next && next !== stops[stops.length - 1]) stops.push(next);
    }
    const chain = stops.filter(Boolean).join(" → ");
    return chain.length <= MAX_TITLE ? chain : `${stops[0]} → ${stops[stops.length - 1]}`;
  }

  if (trip.tripType === "open_jaw") {
    const out = `${city(trip.outboundFlight?.origin)} → ${city(trip.outboundFlight?.destination)}`;
    const back = `${city(trip.returnFlight?.origin)} → ${city(trip.returnFlight?.destination)}`;
    return `${out} · ${back}`;
  }

  return `${city(trip.outboundFlight?.origin)} → ${city(trip.outboundFlight?.destination)}`;
}

/** `Vienna → Tokyo · 7 nights from €421` */
export function tripPreviewTitle(trip: TripOption): string {
  const route = tripRouteLabel(trip);
  const parts = [route];

  if (typeof trip.nights === "number" && trip.nights > 0) {
    parts.push(`${trip.nights} ${trip.nights === 1 ? "night" : "nights"}`);
  }
  if (typeof trip.totalPrice === "number" && trip.totalPrice > 0) {
    parts.push(`from ${money(trip.totalPrice, trip.outboundFlight?.currency ?? "EUR")}`);
  }

  const full = parts.join(" · ");
  return full.length <= MAX_TITLE ? full : route.slice(0, MAX_TITLE);
}

/** `12–19 Oct · observed fare from €421 · check the live price before booking.` */
export function tripPreviewDescription(trip: TripOption): string {
  const parts: string[] = [];

  // A range is printed only when it is coherent. Some cached trips carry a
  // return leg dated the same day as the outbound while reporting several
  // nights — rendering "7 Nov – 7 Nov · 4 nights" would put a visible
  // contradiction in front of whoever the link was sent to. When the dates do
  // not agree with themselves, the departure alone is the honest answer, and
  // the title still carries the length.
  const outRaw = trip.outboundFlight?.departureDateTime;
  const backRaw = trip.returnFlight?.arrivalDateTime ?? trip.returnFlight?.departureDateTime;
  const out = shortDate(outRaw);
  const back = shortDate(backRaw);
  // Compared as calendar days, not instants: a return leg landing at 19:19 on
  // the same date the trip departed is "later" as a timestamp while still
  // rendering as "7 Nov – 7 Nov".
  const coherent =
    Boolean(out && back) && out !== back && new Date(backRaw as string) > new Date(outRaw as string);

  if (out && back && coherent) parts.push(`${out} – ${back}`);
  else if (out) parts.push(out);

  if (typeof trip.totalPrice === "number" && trip.totalPrice > 0) {
    // "observed fare from" and never "book for": the number describes what was
    // seen, not what is on sale.
    parts.push(`observed fare from ${money(trip.totalPrice, trip.outboundFlight?.currency ?? "EUR")}`);
  }

  parts.push("check the live price before booking");
  return `${parts.join(" · ")}.`;
}
