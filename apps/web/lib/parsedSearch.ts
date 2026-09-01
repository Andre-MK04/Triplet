import { airportCity } from "./airports";
import { formatPrice } from "./format";
import type { TripSearchPayload } from "./types";

/**
 * Turn what the AI understood into something a traveller can check.
 *
 * The model reads a sentence and produces a search. When it misreads one —
 * "next October" as this October, "under 900" as a trip length — the only
 * symptom is results that feel subtly wrong, with nothing on screen explaining
 * why. These chips make the interpretation visible, and let the obviously wrong
 * parts be dropped.
 *
 * Everything here is derived from the parsed request the API returned. Nothing
 * re-parses the sentence, so the chips cannot disagree with the search that
 * actually ran — they are a view of it, not a second opinion.
 */

/**
 * The budget the API is given when someone drops the ceiling.
 *
 * The request schema requires a budget, so "no limit" is the highest value the
 * refine panel itself accepts. Lives here so the chip and the search agree on
 * what "dropped" means — otherwise the chip would keep offering to remove a
 * ceiling that is already as high as it goes.
 */
export const MAX_BUDGET_CEILING = 5000;

export type ParsedChipKey =
  | "from"
  | "destination"
  | "when"
  | "length"
  | "budget"
  | "plan"
  | "direct"
  | "outsideEurope"
  | "unvisited";

export type ParsedChip = {
  key: ParsedChipKey;
  label: string;
  value: string;
  /**
   * Whether dropping this constraint is meaningful and safe. Origins, dates and
   * trip length are structural — a search without them is not a broader search,
   * it is not a search — so they are shown but never removable.
   */
  removable: boolean;
  /** What removing it does, for the control's accessible name. */
  removeHint?: string;
};

/** Country codes to names, via the browser's own data rather than a table of ours. */
function countryName(code: string): string {
  try {
    const display = new Intl.DisplayNames(["en"], { type: "region" });
    return display.of(code.toUpperCase()) ?? code.toUpperCase();
  } catch {
    return code.toUpperCase();
  }
}

function titleCase(value: string): string {
  return value
    .split(/[\s_-]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function joinWithLimit(values: string[], limit = 3): string {
  if (values.length <= limit) return values.join(" + ");
  return `${values.slice(0, limit).join(" + ")} +${values.length - limit}`;
}

/** "October", or "October–November" when the window straddles two. */
function describeWindow(start?: string, end?: string): string | null {
  if (!start || !end) return null;
  const from = new Date(start);
  const to = new Date(end);
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return null;

  const month = (d: Date) => d.toLocaleDateString("en-GB", { month: "long" });
  const withYear = (d: Date) => d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });

  if (from.getFullYear() !== to.getFullYear()) return `${withYear(from)}–${withYear(to)}`;
  if (from.getMonth() === to.getMonth()) return month(from);
  // A window spanning more than two months is a range, not a month.
  if (to.getMonth() - from.getMonth() > 2) {
    return `${from.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} – ${to.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
  }
  return `${month(from)}–${month(to)}`;
}

function describeDestination(parsed: TripSearchPayload): string {
  const parts: string[] = [];
  if (parsed.destinationAirports?.length) {
    parts.push(...parsed.destinationAirports.map((code) => airportCity(code) || code));
  }
  if (parsed.destinationCountries?.length) {
    parts.push(...parsed.destinationCountries.map(countryName));
  }
  if (parsed.destinationRegions?.length) {
    parts.push(...parsed.destinationRegions.map(titleCase));
  }
  if (parsed.destinationContinents?.length) {
    parts.push(...parsed.destinationContinents.map(titleCase));
  }
  return parts.length > 0 ? joinWithLimit(parts) : "Anywhere";
}

const PLAN_LABELS: Record<string, string> = {
  return: "Return",
  multi_city: "Multi-city",
  open_jaw: "Open-jaw",
};

export function parsedChips(parsed: TripSearchPayload | null | undefined): ParsedChip[] {
  if (!parsed) return [];
  const chips: ParsedChip[] = [];

  if (parsed.originAirports?.length) {
    chips.push({
      key: "from",
      label: "From",
      value: joinWithLimit(parsed.originAirports.map((code) => airportCity(code) || code)),
      removable: false,
    });
  }

  const hasDestination =
    Boolean(parsed.destinationAirports?.length) ||
    Boolean(parsed.destinationCountries?.length) ||
    Boolean(parsed.destinationRegions?.length) ||
    Boolean(parsed.destinationContinents?.length);

  chips.push({
    key: "destination",
    label: "Destination",
    value: describeDestination(parsed),
    removable: hasDestination,
    removeHint: "search anywhere instead",
  });

  const when = describeWindow(parsed.startDate, parsed.endDate);
  if (when) {
    chips.push({ key: "when", label: "When", value: when, removable: false });
  }

  if (parsed.minTripLengthDays && parsed.maxTripLengthDays) {
    chips.push({
      key: "length",
      label: "Length",
      value:
        parsed.minTripLengthDays === parsed.maxTripLengthDays
          ? `${parsed.minTripLengthDays} days`
          : `${parsed.minTripLengthDays}–${parsed.maxTripLengthDays} days`,
      removable: false,
    });
  }

  if (parsed.maxBudget) {
    // At the ceiling there is nothing left to drop, so the chip reports the
    // budget without offering a removal that would change nothing.
    const atCeiling = parsed.maxBudget >= MAX_BUDGET_CEILING;
    chips.push({
      key: "budget",
      label: "Budget",
      value: atCeiling ? "No limit" : `≤ ${formatPrice(parsed.maxBudget)}`,
      removable: !atCeiling,
      removeHint: "drop the price ceiling",
    });
  }

  if (parsed.tripPlan) {
    chips.push({
      key: "plan",
      label: "Plan",
      value: PLAN_LABELS[parsed.tripPlan] ?? titleCase(parsed.tripPlan),
      removable: false,
    });
  }

  if (parsed.directOnly) {
    chips.push({
      key: "direct",
      label: "Direct",
      value: "Direct flights only",
      removable: true,
      removeHint: "allow connections",
    });
  }

  if (parsed.excludeEurope) {
    chips.push({
      key: "outsideEurope",
      label: "Scope",
      value: "Outside Europe",
      removable: true,
      removeHint: "include Europe",
    });
  }

  if (parsed.unvisitedOnly) {
    chips.push({
      key: "unvisited",
      label: "Scope",
      value: "Somewhere new",
      removable: true,
      removeHint: "include places you have been",
    });
  }

  return chips;
}
