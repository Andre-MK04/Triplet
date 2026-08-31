import type { FlightPlaceResult, TripOption, TripSearchPayload } from "./types";

/**
 * Keeps the last search alive across navigation.
 *
 * Opening a trip and pressing back used to land on an empty Discover page, and
 * the only way to get the list again was to search again — which on the AI path
 * spends one of the traveller's monthly searches to show them something they
 * had already seen. The results are restored instead.
 *
 * sessionStorage rather than a server round trip: the results already belong to
 * this tab, restoring costs nothing, and they disappear when the tab does. It is
 * per-viewer and never leaves the browser.
 */

const STORAGE_KEY = "triplet-last-search";

/**
 * How long a restored list stays usable.
 *
 * Generous on purpose: the store already dies with the tab, and every row shows
 * its own fare age, so a restored list is never passing off old prices as new.
 * The cap exists only to stop a laptop left open overnight reopening to
 * yesterday's search as though it were current.
 */
const MAX_AGE_MS = 12 * 60 * 60 * 1000;

/** Past this, the restored list is flagged rather than shown quietly. */
export const AGEING_AFTER_MS = 2 * 60 * 60 * 1000;

export type RestoredSearch = {
  savedAt: number;
  /** The `?q=` this search answered, so returning does not re-run it. */
  answeredQuery: string | null;
  aiMessage: string;
  trips: TripOption[];
  aiSummary: string;
  aiMissingFields: string[];
  relaxationNote: string | null;
  notice: { text: string; tone: "info" | "warning" } | null;
  lastPayload: TripSearchPayload | null;
  form: unknown;
  destinationSelections: FlightPlaceResult[];
  originLabels: Record<string, string>;
};

export function saveSearch(state: Omit<RestoredSearch, "savedAt">): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...state, savedAt: Date.now() } satisfies RestoredSearch),
    );
  } catch {
    // A full or blocked store is not worth failing a search over — the page
    // simply behaves as it did before, and searching again still works.
  }
}

export function loadSearch(): RestoredSearch | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RestoredSearch;
    if (!parsed?.savedAt || Date.now() - parsed.savedAt > MAX_AGE_MS) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    if (!Array.isArray(parsed.trips) || parsed.trips.length === 0) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearSearch(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do; a stale entry expires on its own.
  }
}

/** How long ago the restored results were fetched. */
export function ageSince(savedAt: number): { label: string; isAgeing: boolean } {
  const elapsed = Math.max(0, Date.now() - savedAt);
  const minutes = Math.floor(elapsed / 60000);
  const label =
    minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago` : `${Math.floor(minutes / 60)} h ago`;
  return { label, isAgeing: elapsed >= AGEING_AFTER_MS };
}
