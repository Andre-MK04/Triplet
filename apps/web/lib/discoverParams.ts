import { isSortKey, type SortKey } from "./sorting";
import type { TripPlan, TripStyle } from "./types";

/**
 * Discover's search state, as something you can paste to someone.
 *
 * Structured searches lived only in component state, so the one thing a person
 * naturally does with a good search — send it to whoever they are travelling
 * with — produced a link to an empty form.
 *
 * Two rules shape everything here.
 *
 * A URL is public. It gets pasted into chat apps, mailed, and logged by every
 * proxy in between, so only search criteria go in it: never an address, an
 * account, a token, or anything about who is searching. The allowlist below is
 * the whole schema, and a field is absent unless it appears in it.
 *
 * A URL is also untrusted input. Anything can arrive in a query string, so
 * every value is validated and anything invalid is dropped rather than thrown
 * over — a mistyped link should open a slightly emptier search, never a broken
 * page.
 */

export type DiscoverSearchState = {
  originAirports: string[];
  destinationAirports: string[];
  destinationCountries: string[];
  destinationRegions: string[];
  destinationContinents: string[];
  excludeEurope: boolean;
  unvisitedOnly: boolean;
  returnOriginAirports: string[];
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: TripStyle;
  tripPlan: TripPlan;
  directOnly: boolean;
};

/** Short, readable, and stable — these appear in links people keep. */
const KEYS = {
  originAirports: "from",
  destinationAirports: "to",
  destinationCountries: "countries",
  destinationRegions: "regions",
  destinationContinents: "continents",
  returnOriginAirports: "backTo",
  startDate: "start",
  endDate: "end",
  minTripLengthDays: "minDays",
  maxTripLengthDays: "maxDays",
  maxBudget: "budget",
  maxGroundTransferHours: "transfer",
  tripStyle: "style",
  tripPlan: "plan",
  directOnly: "direct",
  excludeEurope: "noEurope",
  unvisitedOnly: "unvisited",
  sort: "sort",
} as const;

const IATA = /^[A-Z]{3}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const NAME = /^[\p{L} .'-]{2,60}$/u;

const TRIP_STYLES: TripStyle[] = ["one city", "two nearby cities", "surprise me"];
const TRIP_PLANS: TripPlan[] = ["return", "multi_city", "open_jaw"];

/**
 * Ceilings, so a hand-edited link cannot make the app do unreasonable work.
 * These bound the URL, not the product: the plan entitlement is enforced
 * separately and by the API, which is the only place it can be enforced.
 */
const MAX_CODES = 12;
const MAX_NAMES = 12;
const MAX_BUDGET = 100_000;
const MAX_TRIP_DAYS = 365;
const MAX_TRANSFER_HOURS = 24;

function codes(raw: string | null): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  for (const part of raw.split(",")) {
    const code = part.trim().toUpperCase();
    if (IATA.test(code)) seen.add(code);
    if (seen.size >= MAX_CODES) break;
  }
  return [...seen];
}

function names(raw: string | null): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  for (const part of raw.split(",")) {
    const name = part.trim();
    if (NAME.test(name)) seen.add(name);
    if (seen.size >= MAX_NAMES) break;
  }
  return [...seen];
}

function isoDate(raw: string | null): string | null {
  if (!raw || !ISO_DATE.test(raw)) return null;
  // Rejects 2026-02-31 and similar, which match the shape but are not dates.
  const parsed = new Date(`${raw}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10) === raw ? raw : null;
}

function integer(raw: string | null, min: number, max: number): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  return Number.isFinite(value) && value >= min && value <= max ? value : null;
}

function boolean(raw: string | null): boolean | null {
  if (raw === "true" || raw === "1") return true;
  if (raw === "false" || raw === "0") return false;
  return null;
}

/**
 * Read whatever of a search is present and valid, over a set of defaults.
 *
 * Never throws. A link someone edited by hand, or that a chat app truncated,
 * yields the fields that survived and the defaults for the rest.
 */
export function parseDiscoverSearchParams(
  params: URLSearchParams,
  defaults: DiscoverSearchState,
): DiscoverSearchState {
  const next: DiscoverSearchState = { ...defaults };

  const from = codes(params.get(KEYS.originAirports));
  if (from.length) next.originAirports = from;

  const to = codes(params.get(KEYS.destinationAirports));
  if (to.length) next.destinationAirports = to;

  const backTo = codes(params.get(KEYS.returnOriginAirports));
  if (backTo.length) next.returnOriginAirports = backTo;

  const countries = names(params.get(KEYS.destinationCountries));
  if (countries.length) next.destinationCountries = countries;

  const regions = names(params.get(KEYS.destinationRegions));
  if (regions.length) next.destinationRegions = regions;

  const continents = names(params.get(KEYS.destinationContinents));
  if (continents.length) next.destinationContinents = continents;

  const start = isoDate(params.get(KEYS.startDate));
  if (start) next.startDate = start;

  const end = isoDate(params.get(KEYS.endDate));
  if (end) next.endDate = end;

  const minDays = integer(params.get(KEYS.minTripLengthDays), 1, MAX_TRIP_DAYS);
  if (minDays !== null) next.minTripLengthDays = minDays;

  const maxDays = integer(params.get(KEYS.maxTripLengthDays), 1, MAX_TRIP_DAYS);
  if (maxDays !== null) next.maxTripLengthDays = maxDays;

  // A reversed range is a mistyped link, not a request for no results.
  if (next.maxTripLengthDays < next.minTripLengthDays) {
    next.maxTripLengthDays = next.minTripLengthDays;
  }

  const budget = integer(params.get(KEYS.maxBudget), 1, MAX_BUDGET);
  if (budget !== null) next.maxBudget = budget;

  const transfer = integer(params.get(KEYS.maxGroundTransferHours), 0, MAX_TRANSFER_HOURS);
  if (transfer !== null) next.maxGroundTransferHours = transfer;

  const style = params.get(KEYS.tripStyle);
  if (style && (TRIP_STYLES as string[]).includes(style)) next.tripStyle = style as TripStyle;

  const plan = params.get(KEYS.tripPlan);
  if (plan && (TRIP_PLANS as string[]).includes(plan)) next.tripPlan = plan as TripPlan;

  const direct = boolean(params.get(KEYS.directOnly));
  if (direct !== null) next.directOnly = direct;

  const noEurope = boolean(params.get(KEYS.excludeEurope));
  if (noEurope !== null) next.excludeEurope = noEurope;

  const unvisited = boolean(params.get(KEYS.unvisitedOnly));
  if (unvisited !== null) next.unvisitedOnly = unvisited;

  return next;
}

/**
 * Write a search back out, omitting anything left at its default.
 *
 * Omitting defaults keeps shared links short and readable, and means a link
 * says what someone actually chose rather than restating the whole form.
 */
export function serializeDiscoverSearchParams(
  state: DiscoverSearchState,
  defaults: DiscoverSearchState,
  extra?: { sort?: SortKey | null; query?: string | null },
): URLSearchParams {
  const params = new URLSearchParams();

  const list = (key: string, value: string[], fallback: string[]) => {
    if (value.length && value.join(",") !== fallback.join(",")) params.set(key, value.join(","));
  };
  const scalar = (key: string, value: string | number | boolean, fallback: typeof value) => {
    if (value !== fallback) params.set(key, String(value));
  };

  list(KEYS.originAirports, state.originAirports, defaults.originAirports);
  list(KEYS.destinationAirports, state.destinationAirports, defaults.destinationAirports);
  list(KEYS.returnOriginAirports, state.returnOriginAirports, defaults.returnOriginAirports);
  list(KEYS.destinationCountries, state.destinationCountries, defaults.destinationCountries);
  list(KEYS.destinationRegions, state.destinationRegions, defaults.destinationRegions);
  list(KEYS.destinationContinents, state.destinationContinents, defaults.destinationContinents);

  scalar(KEYS.startDate, state.startDate, defaults.startDate);
  scalar(KEYS.endDate, state.endDate, defaults.endDate);
  scalar(KEYS.minTripLengthDays, state.minTripLengthDays, defaults.minTripLengthDays);
  scalar(KEYS.maxTripLengthDays, state.maxTripLengthDays, defaults.maxTripLengthDays);
  scalar(KEYS.maxBudget, state.maxBudget, defaults.maxBudget);
  scalar(KEYS.maxGroundTransferHours, state.maxGroundTransferHours, defaults.maxGroundTransferHours);
  scalar(KEYS.tripStyle, state.tripStyle, defaults.tripStyle);
  scalar(KEYS.tripPlan, state.tripPlan, defaults.tripPlan);
  scalar(KEYS.directOnly, state.directOnly, defaults.directOnly);
  scalar(KEYS.excludeEurope, state.excludeEurope, defaults.excludeEurope);
  scalar(KEYS.unvisitedOnly, state.unvisitedOnly, defaults.unvisitedOnly);

  if (extra?.sort && isSortKey(extra.sort)) params.set(KEYS.sort, extra.sort);
  if (extra?.query) params.set("q", extra.query);

  return params;
}

/** The shareable address of a search, ready to hand to someone. */
export function discoverShareUrl(
  state: DiscoverSearchState,
  defaults: DiscoverSearchState,
  extra?: { sort?: SortKey | null; query?: string | null },
  origin?: string,
): string {
  const params = serializeDiscoverSearchParams(state, defaults, extra);
  const base = `${origin ?? (typeof window === "undefined" ? "" : window.location.origin)}/discover`;
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}
