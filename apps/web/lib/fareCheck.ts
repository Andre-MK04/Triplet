import type { TripOption } from "./types";

/**
 * Remembering that someone went to check a fare, so Triplet can ask how it went.
 *
 * Triplet shows observed prices and says so, but "recently observed" is a
 * promise it has never been able to size. The only people who can size it are
 * travellers who followed a live-price link and saw what was actually there.
 *
 * Everything here stays in this browser until the traveller answers. Nothing is
 * sent when they click — a click is not consent to be measured — and what is
 * sent on answering describes the fare, never them.
 */

const STORAGE_KEY = "triplet.fareChecks.v1";
const LAST_ASKED_KEY = "triplet.fareChecks.lastAsked.v1";

/** Long enough to have looked; short enough to still remember what was seen. */
export const ASK_AFTER_MS = 90_000;
/** After this, they will not remember reliably and the answer is noise. */
export const ASK_BEFORE_MS = 3 * 24 * 60 * 60 * 1000;
/** At most one question a day, however many fares get checked. */
export const MIN_MS_BETWEEN_ASKS = 20 * 60 * 60 * 1000;
/** Nothing is worth remembering more than a handful of checks back. */
const MAX_STORED = 8;

export type FareCheckResponse = "matched" | "slightly_higher" | "much_higher" | "unavailable";

export type PendingFareCheck = {
  checkId: string;
  clickedAt: number;
  /** Enough to describe the fare that was checked, and nothing more. */
  origin: string;
  destination: string;
  originCity: string;
  destinationCity: string;
  tripType: string;
  fareKind: string;
  fareAgeBucket: string;
  shownPrice: number;
  currency: string;
  provider?: string | null;
  /** Set once answered or dismissed, so it is never raised again. */
  settled?: boolean;
};

function read(): PendingFareCheck[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as PendingFareCheck[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(checks: PendingFareCheck[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(checks.slice(-MAX_STORED)));
  } catch {
    // A full or disabled store costs a research signal, nothing a traveller needs.
  }
}

function newCheckId(): string {
  const cryptoObj = typeof window !== "undefined" ? window.crypto : undefined;
  if (cryptoObj?.randomUUID) return cryptoObj.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Note that a traveller has gone to check this fare.
 *
 * Called as the live-price link is followed. Records locally only — nothing
 * reaches Triplet unless they later answer.
 */
export function rememberFareCheck(trip: TripOption): void {
  const price = trip.price;
  if (!price) return;

  const check: PendingFareCheck = {
    checkId: newCheckId(),
    clickedAt: Date.now(),
    origin: trip.outboundFlight.origin,
    destination: trip.outboundFlight.destination,
    originCity: trip.destination?.city ? trip.outboundFlight.origin : trip.outboundFlight.origin,
    destinationCity: trip.destination?.city ?? trip.outboundFlight.destination,
    tripType: trip.tripType,
    fareKind: price.kind,
    fareAgeBucket: price.freshness ?? "unknown",
    shownPrice: trip.totalPrice,
    currency: price.currency ?? "EUR",
    provider: trip.provider ?? null,
  };
  write([...read().filter((c) => !c.settled), check]);
}

/**
 * The one check worth asking about now, if any.
 *
 * At most one at a time and at most one a day: a research signal is not worth
 * making the product feel like it is interviewing people. Returns null far more
 * often than not, on purpose.
 */
export function fareCheckToAsk(now = Date.now()): PendingFareCheck | null {
  const checks = read();
  if (checks.length === 0) return null;

  if (typeof window !== "undefined") {
    try {
      const lastAsked = Number(window.localStorage.getItem(LAST_ASKED_KEY) ?? 0);
      if (lastAsked && now - lastAsked < MIN_MS_BETWEEN_ASKS) return null;
    } catch {
      return null;
    }
  }

  const ripe = checks.filter(
    (check) =>
      !check.settled &&
      now - check.clickedAt >= ASK_AFTER_MS &&
      now - check.clickedAt <= ASK_BEFORE_MS,
  );
  // The most recent, because it is the one they remember best.
  return ripe.length > 0 ? ripe[ripe.length - 1] : null;
}

/** Mark a check answered or dismissed. Either way it is never raised again. */
export function settleFareCheck(checkId: string, now = Date.now()): void {
  write(read().map((check) => (check.checkId === checkId ? { ...check, settled: true } : check)));
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAST_ASKED_KEY, String(now));
  } catch {
    // Nothing to do; the ask cadence degrades, which is harmless.
  }
}

/** Drop everything. Used when someone asks not to be asked again. */
export function forgetAllFareChecks(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.setItem(LAST_ASKED_KEY, String(Date.now()));
  } catch {
    // Ignored.
  }
}
