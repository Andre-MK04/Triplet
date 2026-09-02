"use client";

import { useEffect, useState } from "react";

import { apiGet } from "./api";

/**
 * How many origin airports this visitor may search with.
 *
 * The backend refuses an over-limit search with a 402 rather than quietly
 * trimming it, so an interface that lets someone pick a seventh airport has
 * only moved the refusal later — past the point where they thought they were
 * done. The picker needs the number in order not to offer what it knows will
 * be rejected.
 *
 * The number is read from the API in both cases rather than written down here.
 * Every limit is environment-overridable, so a copy in the frontend would be a
 * second source of truth that is right until someone changes the first one.
 */
export type OriginLimit = {
  /** The ceiling, once known. */
  max: number;
  /**
   * False until the limit has been fetched, and permanently false if it could
   * not be. Callers must not restrict anything while this is false: failing to
   * learn the limit is a reason to let the backend answer, exactly as it did
   * before this existed, not a reason to lock someone out of their own search.
   */
  known: boolean;
  /** "Free", "Pro", or null when signed out. Used to explain the ceiling. */
  planName: string | null;
  /** Whether an upgrade would actually raise it. */
  canRaise: boolean;
};

const UNKNOWN: OriginLimit = {
  // Deliberately permissive. Nothing is blocked while `known` is false, and
  // this value is never shown; it only keeps comparisons total.
  max: Number.POSITIVE_INFINITY,
  known: false,
  planName: null,
  canRaise: false,
};

const PLAN_NAMES: Record<string, string> = {
  free: "Free",
  trial: "the Pro trial",
  pro: "Pro",
};

type PlansPayload = { anonymousMaxOriginAirports?: number };
type StatusPayload = {
  plan?: string;
  limits?: { maxOriginAirports?: number | string; unlimited?: boolean };
  canUpgrade?: boolean;
};

export function useOriginLimit(signedIn: boolean): OriginLimit {
  const [limit, setLimit] = useState<OriginLimit>(UNKNOWN);

  useEffect(() => {
    let cancelled = false;

    // Reset when identity changes: a signed-out limit must not linger as
    // though it applied to the account that just signed in.
    setLimit(UNKNOWN);

    const load = signedIn
      ? apiGet<StatusPayload>("/billing/status").then((status) => {
          const raw = status.limits?.maxOriginAirports;
          // Owner accounts and Pro report an unlimited sentinel rather than a
          // number; there is nothing to cap in that case.
          if (status.limits?.unlimited || typeof raw !== "number") return UNKNOWN;
          return {
            max: raw,
            known: true,
            planName: PLAN_NAMES[status.plan ?? ""] ?? null,
            canRaise: Boolean(status.canUpgrade),
          };
        })
      : apiGet<PlansPayload>("/billing/plans").then((plans) => {
          const raw = plans.anonymousMaxOriginAirports;
          if (typeof raw !== "number") return UNKNOWN;
          return { max: raw, known: true, planName: null, canRaise: true };
        });

    load
      .then((next) => {
        if (!cancelled) setLimit(next);
      })
      .catch(() => {
        // Leave it unknown. The search still works; the backend still answers.
      });

    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  return limit;
}

/**
 * Whether one more airport can be added.
 *
 * Selecting is blocked at the ceiling, but a selection that is *already* over
 * it is never trimmed automatically — a lapsed trial can leave someone holding
 * eight airports, and silently discarding five of them would be a worse
 * surprise than the message explaining it.
 */
export function canAddOrigin(limit: OriginLimit, selectedCount: number): boolean {
  if (!limit.known) return true;
  return selectedCount < limit.max;
}

/** Plain wording for why nothing more can be added, or null when it can. */
export function originLimitMessage(
  limit: OriginLimit,
  selectedCount: number,
): string | null {
  if (!limit.known) return null;

  const airports = `${limit.max} origin ${limit.max === 1 ? "airport" : "airports"}`;

  if (selectedCount > limit.max) {
    return limit.planName
      ? `${selectedCount} airports selected, but ${limit.planName} searches up to ${airports}. Remove ${selectedCount - limit.max} to search.`
      : `${selectedCount} airports selected, but signed-out search allows ${airports}. Remove ${selectedCount - limit.max} to search.`;
  }

  if (selectedCount < limit.max) return null;

  return limit.planName
    ? `That's all ${airports} ${limit.planName} includes.`
    : `Signed-out search covers ${airports}. Sign in to use more.`;
}
