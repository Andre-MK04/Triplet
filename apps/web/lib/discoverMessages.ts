import { ApiError } from "./api";
import type { ProviderMetadata, TripSearchPayload } from "./types";

/**
 * What Discover says when a search does not simply work.
 *
 * These three decide what a traveller believes about a result: whether prices
 * are live, whether an empty page means Triplet did not look or the fares are
 * not there, and whether an error is their problem or ours. They lived inside a
 * thousand-line client component where none of them could be tested; the
 * judgements are the same, now checkable.
 */

export type SearchNotice = { text: string; tone: "info" | "warning" };

/**
 * Whether to caveat where these prices came from.
 *
 * Triplet must never present cached or demo fares as though a live source had
 * answered, so a failed live attempt is a warning and development data is
 * always labelled.
 */
export function providerNotice(
  metadata?: ProviderMetadata | null,
  tripCount = 0,
): SearchNotice | null {
  if (!metadata) return null;
  const warnings = metadata.providerWarnings ?? [];

  if (metadata.liveProviderAttempted && !metadata.liveProviderSucceeded) {
    return {
      tone: "warning",
      text:
        warnings[0] ??
        // Not "live fares were unavailable": Triplet has no live fare feed, so
        // saying that implies a capability it does not have and makes the
        // fallback sound like a degraded version of something better.
        "Couldn't reach the fare provider — showing fares Triplet observed earlier, which may be out of date.",
    };
  }
  if (metadata.cachedResultsUsed && !metadata.liveProviderSucceeded) {
    return {
      tone: "info",
      text: "Showing demo/cached fares from the development dataset. Prices are illustrative, not live.",
    };
  }
  if (warnings.length > 0 && tripCount > 0) {
    return { tone: "info", text: warnings[0] };
  }
  return null;
}

/**
 * Why a search found nothing.
 *
 * The distinction that matters: when a traveller named a destination, Triplet
 * did ask the fare data about it and there was nothing for those dates. Falling
 * back to "try more origin airports" would imply a limit of Triplet's rather
 * than a thinness of the fares, and send them to fix the wrong thing.
 */
export function emptyStateMessage(payload: TripSearchPayload | null): string {
  const namedPlace = (payload?.destinationAirports?.length ?? 0) > 0;
  const namedScope =
    (payload?.destinationCountries?.length ?? 0) > 0 ||
    (payload?.destinationRegions?.length ?? 0) > 0 ||
    (payload?.destinationContinents?.length ?? 0) > 0;

  if (namedPlace || namedScope) {
    return `We checked ${
      namedPlace ? "that destination" : "those countries"
    } directly and found no round trips in your dates and trip length. Long-haul fares are often thin outside a few months — try a wider date window, a longer trip, or a higher budget.`;
  }
  if (payload?.excludeEurope) {
    return "No long-haul fares outside Europe matched these dates and budget. Long-haul rarely fits short windows — try a wider date range and a longer trip.";
  }
  return "Try widening the budget, adding more origin airports, or allowing longer ground transfers.";
}

/**
 * An error a traveller can act on.
 *
 * A quota message from the API is already specific about trials and plans, so
 * it is passed through rather than flattened into something generic.
 */
export function limitAwareError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 402) return error.message;
    if (error.status === 429) return "You're searching fast! Give it a few seconds and try again.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}
