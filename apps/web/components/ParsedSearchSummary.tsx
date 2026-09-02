"use client";

import { parsedChips, type ParsedChipKey } from "../lib/parsedSearch";
import type { TripSearchPayload } from "../lib/types";

/**
 * What Triplet understood, in the traveller's words rather than the parser's.
 *
 * Deliberately not raw parser output: a JSON blob is inspectable only by
 * someone who already knows the schema, and the point is for anyone to notice
 * that "next October" was read as this one.
 *
 * Removing a chip re-runs the search with that constraint dropped, through the
 * structured endpoint — so correcting a misreading does not spend another AI
 * search, which is the thing that would make people hesitate to correct it.
 */
export function ParsedSearchSummary({
  parsed,
  onRemove,
  isBusy = false,
}: {
  parsed: TripSearchPayload | null | undefined;
  onRemove?: (key: ParsedChipKey) => void;
  isBusy?: boolean;
}) {
  const chips = parsedChips(parsed);
  if (chips.length === 0) return null;

  return (
    <section aria-labelledby="parsed-summary-heading" className="border-b border-line pb-4">
      <h2
        id="parsed-summary-heading"
        className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist"
      >
        What Triplet understood
      </h2>

      <ul className="mt-3 flex flex-wrap gap-2">
        {chips.map((chip) => (
          <li key={`${chip.key}-${chip.value}`}>
            <span className="inline-flex items-stretch border border-line">
              <span className="flex flex-col justify-center px-3 py-1.5">
                <span className="font-mono text-[10px] uppercase tracking-label text-mist-dim">
                  {chip.label}
                </span>
                <span className="text-sm leading-tight text-cloud">{chip.value}</span>
              </span>
              {chip.removable && onRemove ? (
                <button
                  type="button"
                  onClick={() => onRemove(chip.key)}
                  disabled={isBusy}
                  // Says what it drops, not just "remove": a bare × beside
                  // "Destination Japan" reads identically to every other × on
                  // the row when heard rather than seen.
                  aria-label={`Remove ${chip.label.toLowerCase()} ${chip.value} — ${chip.removeHint}`}
                  title={chip.removeHint}
                  className="border-l border-line px-2.5 font-mono text-sm text-mist transition-colors hover:bg-coral/10 hover:text-coral disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ×
                </button>
              ) : null}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-2.5 text-xs leading-relaxed text-mist-dim">
        Read from your request by AI. Drop anything it got wrong — that runs a fresh search without
        using one of your AI searches.
      </p>
    </section>
  );
}
