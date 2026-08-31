import { formatPrice } from "./format";
import type { PriceHistory, TripOption } from "./types";

/**
 * The single place Triplet turns a price into words.
 *
 * Travelpayouts fares are recently observed prices, not live inventory, so the
 * interface never states a bare figure as though it were purchasable. "from"
 * marks an observation, "Estimated from" marks a total we assembled out of
 * several observations, and the secondary line carries the age when it is old
 * enough to matter.
 */

export type PriceConfidence = "fresh" | "recent" | "aging" | "stale" | "unknown";

export type PricePresentation = {
  /** The headline, e.g. "from €72" or "Estimated from €214". */
  primary: string;
  /** Small supporting line, e.g. "Found 14h ago". Empty when nothing to add. */
  secondary: string;
  confidence: PriceConfidence;
  /** True when the figure is a sum of separately observed fares. */
  isEstimate: boolean;
  /** True when the fare is too old to headline as a firm figure. */
  isStale: boolean;
};

function agePhrase(ageHours: number | null | undefined): string {
  if (ageHours == null) return "";
  if (ageHours < 1) return "Found just now";
  if (ageHours < 24) return `Found ${Math.round(ageHours)}h ago`;
  const days = Math.round(ageHours / 24);
  return days === 1 ? "Found yesterday" : `Found ${days} days ago`;
}

export function pricePresentation(trip: TripOption): PricePresentation {
  const info = trip.price;
  const amount = formatPrice(trip.totalPrice);

  // Older results built before the price model existed, and any future source
  // that does not populate it, still render sensibly.
  if (!info) {
    return {
      primary: `from ${amount}`,
      secondary: "",
      confidence: "unknown",
      isEstimate: false,
      isStale: false,
    };
  }

  const confidence = info.freshness;
  const isStale = confidence === "stale";
  const money = formatPrice(info.amount, info.currency);

  if (info.isEstimate) {
    return {
      primary: `Estimated from ${money}`,
      secondary: isStale
        ? "Based on older fares — check current prices"
        : info.legCount > 1
          ? `${info.legCount} flights priced separately`
          : agePhrase(info.ageHours),
      confidence,
      isEstimate: true,
      isStale,
    };
  }

  if (isStale) {
    return {
      primary: `recently from ${money}`,
      secondary: "Price may have changed",
      confidence,
      isEstimate: false,
      isStale: true,
    };
  }

  if (confidence === "aging") {
    return {
      primary: `recently from ${money}`,
      secondary: "Price may have changed",
      confidence,
      isEstimate: false,
      isStale: false,
    };
  }

  return {
    primary: `from ${money}`,
    secondary: confidence === "unknown" ? "" : agePhrase(info.ageHours),
    confidence,
    isEstimate: false,
    isStale: false,
  };
}

/** What the button says. Triplet finds the candidate; Aviasales confirms the fare. */
export const CHECK_PRICE_LABEL = "Check live price";

export const PRICE_DISCLAIMER =
  "Prices are recently observed fares and may change. Check the airline or agency for current availability.";


/**
 * Whether Triplet's own history justifies calling this a good price, and what
 * to call it.
 *
 * Two gates, both deliberate. Only positive verdicts are surfaced — Triplet is
 * a discovery product, and telling someone their fare is "very high" helps
 * nobody find a trip. And nothing is shown below medium confidence, because a
 * badge drawn from five sightings teaches travellers to distrust the ones drawn
 * from four hundred.
 */
const BADGE_LABELS: Partial<Record<NonNullable<PriceHistory["classification"]>, string>> = {
  exceptional: "Exceptional fare",
  great: "Great price",
  good: "Good price",
};

export type PriceBadge = { label: string; explanation: string };

export function priceBadge(trip: TripOption): PriceBadge | null {
  const history = trip.price?.history;
  if (!history?.available || !history.classification) return null;
  if (history.confidence !== "medium" && history.confidence !== "high") return null;

  const label = BADGE_LABELS[history.classification];
  if (!label) return null;

  const range =
    history.typicalLow != null && history.typicalHigh != null
      ? `Typical recently observed: ${formatPrice(history.typicalLow)}–${formatPrice(history.typicalHigh)}`
      : "";
  return {
    label,
    explanation: range
      ? `${formatPrice(trip.totalPrice)} is lower than most fares Triplet has recorded for similar trips. ${range}.`
      : `${formatPrice(trip.totalPrice)} is lower than most fares Triplet has recorded for similar trips.`,
  };
}
