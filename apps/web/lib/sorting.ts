import type { TripOption } from "./types";

/**
 * How results can be ordered.
 *
 * "Best" is Triplet's own ranking and stays the default: it is the only order
 * that weighs quality, price, freshness and fit together. The others exist
 * because a traveller sometimes has one axis in mind, and a ranking they cannot
 * override is a ranking they have to take on trust.
 */
export type SortKey = "best" | "cheapest" | "freshest" | "fastest";

export const SORT_OPTIONS: { key: SortKey; label: string; hint: string }[] = [
  { key: "best", label: "Best", hint: "Triplet's ranking: quality, price, freshness and fit" },
  { key: "cheapest", label: "Cheapest", hint: "Lowest comparable trip total" },
  { key: "freshest", label: "Freshest", hint: "Most recently observed fare" },
  { key: "fastest", label: "Fastest", hint: "Least time in the air" },
];

export function isSortKey(value: string | null | undefined): value is SortKey {
  return SORT_OPTIONS.some((option) => option.key === value);
}

/**
 * Total flying time, or null when any leg does not report it.
 *
 * Null rather than a partial sum on purpose: adding up the legs that happen to
 * carry a duration would rank a trip as fast on the strength of the one leg we
 * know about, which is worse than admitting we cannot say.
 */
export function totalDurationMinutes(trip: TripOption): number | null {
  const flights = trip.segments?.length
    ? trip.segments.filter((s) => s.kind === "flight").map((s) => s.flight)
    : [trip.outboundFlight, trip.returnFlight];

  let total = 0;
  for (const flight of flights) {
    const minutes = flight?.durationMinutes;
    if (typeof minutes !== "number" || minutes <= 0) return null;
    total += minutes;
  }
  return total > 0 ? total : null;
}

/** Age of the weakest leg, in hours. Lower is fresher. Null when unknown. */
function observedAgeHours(trip: TripOption): number | null {
  const age = trip.price?.ageHours;
  return typeof age === "number" ? age : null;
}

/**
 * Order a result set.
 *
 * Trips missing the value a sort needs always fall to the end rather than
 * sorting as zero — a trip with no duration is not the fastest one.
 */
export function sortTrips(trips: TripOption[], key: SortKey): TripOption[] {
  const sorted = [...trips];

  if (key === "cheapest") {
    return sorted.sort((a, b) => a.totalPrice - b.totalPrice);
  }

  if (key === "freshest") {
    return sorted.sort((a, b) => {
      const ageA = observedAgeHours(a);
      const ageB = observedAgeHours(b);
      if (ageA === null && ageB === null) return 0;
      if (ageA === null) return 1;
      if (ageB === null) return -1;
      return ageA - ageB;
    });
  }

  if (key === "fastest") {
    return sorted.sort((a, b) => {
      const durationA = totalDurationMinutes(a);
      const durationB = totalDurationMinutes(b);
      if (durationA === null && durationB === null) return 0;
      if (durationA === null) return 1;
      if (durationB === null) return -1;
      return durationA - durationB;
    });
  }

  // Best: Triplet's own score, highest first, price breaking ties.
  return sorted.sort((a, b) => {
    const scoreA = a.dealScore ?? a.score;
    const scoreB = b.dealScore ?? b.score;
    if (scoreB !== scoreA) return scoreB - scoreA;
    return a.totalPrice - b.totalPrice;
  });
}

/** How many trips cannot be ordered by this key, so the UI can say so. */
export function unsortableCount(trips: TripOption[], key: SortKey): number {
  if (key === "fastest") return trips.filter((t) => totalDurationMinutes(t) === null).length;
  if (key === "freshest") return trips.filter((t) => observedAgeHours(t) === null).length;
  return 0;
}
