"use client";

import { useMemo, useState } from "react";

import { isSortKey, sortTrips, type SortKey } from "../lib/sorting";
import type { TripOption } from "../lib/types";

/**
 * Result ordering, and keeping it in the URL.
 *
 * Ordering is a view concern: it re-sorts what came back rather than searching
 * again, so it costs nothing and needs no loading state. Everything it touches
 * lives here — nothing outside needs to know an ordering changed except the
 * list that renders it.
 */
export function useSearchSorting(trips: TripOption[], initialSort?: string | null) {
  const [sort, setSort] = useState<SortKey>(() =>
    isSortKey(initialSort) ? initialSort : "best",
  );

  function changeSort(next: SortKey) {
    setSort(next);
    // Reflect the ordering in the URL so it survives a reload and can be
    // shared. replaceState rather than a router push: reordering results is not
    // a navigation and should not add a back-button step.
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (next === "best") url.searchParams.delete("sort");
    else url.searchParams.set("sort", next);
    window.history.replaceState({}, "", url);
  }

  const sortedTrips = useMemo(() => sortTrips(trips, sort), [trips, sort]);

  return { sort, changeSort, sortedTrips };
}
