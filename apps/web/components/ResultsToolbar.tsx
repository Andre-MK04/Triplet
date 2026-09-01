"use client";

import { useEffect, useRef, useState } from "react";

import { SORT_OPTIONS, type SortKey, unsortableCount } from "../lib/sorting";
import type { TripOption } from "../lib/types";

/**
 * The bar above the results: how many, in what order, and why that order.
 *
 * "Best first" used to be stated with no way to find out what best meant. A
 * ranking a traveller cannot inspect is one they have to take on trust, which
 * is exactly what Triplet asks them not to do with prices.
 */
export function ResultsToolbar({
  trips,
  sort,
  onSortChange,
  children,
}: {
  trips: TripOption[];
  sort: SortKey;
  onSortChange: (key: SortKey) => void;
  /** Trailing content, e.g. the watch-this-search action. */
  children?: React.ReactNode;
}) {
  const [explaining, setExplaining] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const missing = unsortableCount(trips, sort);

  // Escape closes and focus returns to the control that opened it.
  useEffect(() => {
    if (!explaining) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setExplaining(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [explaining]);

  return (
    <div className="border-b border-line pb-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
          Results · {trips.length} trip{trips.length === 1 ? "" : "s"} identified
        </p>
        {children}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2">
        <span
          id="sort-label"
          className="mr-1 font-mono text-[11px] uppercase tracking-label text-mist/70"
        >
          Sort
        </span>
        <div role="group" aria-labelledby="sort-label" className="flex flex-wrap gap-1">
          {SORT_OPTIONS.map((option) => {
            const active = option.key === sort;
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => onSortChange(option.key)}
                aria-pressed={active}
                title={option.hint}
                className={
                  "border px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-label transition " +
                  (active
                    ? "border-mint bg-mint text-mint-ink"
                    : "border-line text-mist hover:border-mint/40 hover:text-cloud")
                }
              >
                {option.label}
              </button>
            );
          })}
        </div>

        <button
          ref={triggerRef}
          type="button"
          onClick={() => setExplaining((open) => !open)}
          aria-expanded={explaining}
          aria-controls="ranking-explainer"
          className="ml-1 font-mono text-[11px] uppercase tracking-label text-mist underline transition-colors hover:text-mint"
        >
          How Triplet ranks
        </button>
      </div>

      {missing > 0 ? (
        <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-gold">
          {missing} trip{missing === 1 ? "" : "s"} without{" "}
          {sort === "fastest" ? "a known duration" : "an observed time"} — shown last
        </p>
      ) : null}

      {explaining ? (
        <div
          id="ranking-explainer"
          ref={dialogRef}
          role="region"
          aria-label="How Triplet ranks results"
          tabIndex={-1}
          className="mt-3 border-l-2 border-mint/40 pl-4 text-sm leading-relaxed text-mist"
        >
          <p className="text-cloud">Best first means Triplet&apos;s own ranking, which weighs:</p>
          <ul className="mt-2 space-y-1.5">
            <li>
              <strong className="text-cloud">Trip quality</strong> — how good the trip itself is:
              stops, trip length, how well the dates and destination fit what you asked for.
              This carries the most weight.
            </li>
            <li>
              <strong className="text-cloud">How fresh the fare is</strong> — a price observed an
              hour ago is worth more than one from two days ago, because it is likelier to still
              be there. For a multi-leg trip the oldest leg sets the grade.
            </li>
            <li>
              <strong className="text-cloud">Price</strong> — how this fare compares with the
              others in the same result set, and with prices Triplet has recorded for similar
              trips before.
            </li>
            <li>
              <strong className="text-cloud">Fit</strong> — your travel profile, when you have
              one: preferred trip length, budget comfort, and your comfort rules.
            </li>
          </ul>
          <p className="mt-3">
            Cheapness alone does not win. A very cheap fare that Triplet last saw two days ago
            can rank below a slightly dearer one seen this morning, because the older price is
            likelier to have moved.
          </p>
          <p className="mt-3 text-cloud">
            Commission never affects ranking. Whether a result earns Triplet money is not one of
            the inputs, and there are tests that fail if it becomes one.
          </p>
        </div>
      ) : null}
    </div>
  );
}
