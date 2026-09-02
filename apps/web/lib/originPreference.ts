/**
 * Where this browser can fly from, when there is no account to ask.
 *
 * Triplet was built around a Central European origin list — Vienna, Zagreb,
 * Trieste, Venice, Budapest, Ljubljana — and quietly applied it to everyone.
 * Someone opening Discover from Lisbon got six airports they cannot reach,
 * presented as though Triplet knew something about them.
 *
 * So origins are never assumed. A signed-in traveller has a travel profile; an
 * anonymous one is asked once and remembered here. Until either exists there
 * are no origins at all, and the interface says so rather than guessing.
 *
 * Nothing here is sent anywhere. Location is never requested: an approximate
 * position would be a decent guess and a bad trade, and Triplet does not make
 * that trade on a first visit without being asked.
 */

const STORAGE_KEY = "triplet.origins.v1";

/** IATA codes are three letters. Anything else did not come from the picker. */
const IATA = /^[A-Z]{3}$/;

/** More than this is not a preference, it is a stuck writer. */
const MAX_ORIGINS = 12;

/**
 * The origins this browser has chosen, or an empty list.
 *
 * Storage is read defensively rather than trusted: it is shared with everything
 * else on the origin, survives across versions of this code, and a private
 * window can throw on access rather than return nothing.
 */
export function readSavedOrigins(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return sanitize(parsed);
  } catch {
    return [];
  }
}

/**
 * Remember what was chosen, or forget it when the list is emptied.
 *
 * Clearing on empty matters: someone who deselects every airport has said they
 * do not want these, and leaving the old list to reappear next visit would
 * override them with a stale answer.
 */
export function saveOrigins(codes: string[]): void {
  if (typeof window === "undefined") return;
  const clean = sanitize(codes);
  try {
    if (clean.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
  } catch {
    // A browser refusing to store this is not a reason to fail a search.
  }
}

export function forgetSavedOrigins(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do; the value is unreachable either way.
  }
}

function sanitize(codes: unknown[]): string[] {
  const seen = new Set<string>();
  for (const code of codes) {
    if (typeof code !== "string") continue;
    const upper = code.toUpperCase();
    if (!IATA.test(upper)) continue;
    seen.add(upper);
    if (seen.size >= MAX_ORIGINS) break;
  }
  return [...seen];
}
