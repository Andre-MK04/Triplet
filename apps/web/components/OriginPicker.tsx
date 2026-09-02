"use client";

import { useEffect, useRef, useState } from "react";

import { Autocomplete } from "./Autocomplete";
import { Chip } from "./ui/Chip";
import { AIRPORTS_BY_CODE, ORIGIN_AIRPORT_CODES } from "../lib/airports";
import type { AirportResult } from "../lib/types";

const originsEndpoint = (query: string) =>
  `/airports/search?q=${query}&limit=8&originsOnly=true`;

/** Where the traveller would fly out of — collapsed to one line until opened. */
export function OriginPicker({
  selected,
  labels,
  onToggle,
  onAdd,
}: {
  selected: string[];
  labels: Record<string, string>;
  onToggle: (code: string) => void;
  onAdd: (airport: AirportResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent) {
      if (panel.current && !panel.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const name = (code: string) => labels[code] ?? AIRPORTS_BY_CODE[code]?.city ?? code;

  // With nothing chosen this is not a summary of anything — it is the first
  // question Triplet has to ask. "Your origin airports (0)" claimed a set that
  // did not exist and gave no hint that picking one was the next move.
  const needsSetup = selected.length === 0;
  const summary =
    selected.length === 0
      ? "No airports selected"
      : selected.length <= 2
        ? selected.map(name).join(" · ")
        : `${name(selected[0])} +${selected.length - 1} more`;

  return (
    <div className="relative min-w-0" ref={panel}>
      <p
        className={
          "mb-2.5 font-mono text-[10px] font-semibold uppercase tracking-label " +
          (needsSetup ? "text-mint" : "text-mist")
        }
      >
        {needsSetup ? "Where can you fly from?" : "Flying from"}
      </p>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className={
          "flex w-full items-center justify-between gap-3 border px-3.5 py-2.5 text-left transition-colors " +
          (open || needsSetup
            ? "border-mint text-cloud"
            : "border-line text-cloud hover:border-mint/40")
        }
      >
        <span className="min-w-0 truncate text-sm">
          {needsSetup ? "Choose your departure airports" : "Your origin airports"}
          {needsSetup ? null : <span className="ml-2 text-mist">({selected.length})</span>}
        </span>
        <span className="shrink-0 font-mono text-[11px] uppercase tracking-label text-mist">
          {open ? "Close" : summary}
        </span>
      </button>

      {open ? (
        <div className="absolute left-0 right-0 z-20 mt-1 border border-line bg-ink-raised p-4 shadow-xl">
          {/* Named as the sample it is. These are Central European airports
              because that is where Triplet's fare history is densest, not
              because the person reading this lives near them — the search box
              below reaches every European airport. */}
          <p className="mb-2 font-mono text-[10px] uppercase tracking-label text-mist-dim">
            Common Central European origins
          </p>
          <div className="flex flex-wrap gap-2">
            {[...new Set([...ORIGIN_AIRPORT_CODES, ...selected])].map((code) => (
              <Chip key={code} selected={selected.includes(code)} onClick={() => onToggle(code)}>
                {name(code)} {code}
              </Chip>
            ))}
          </div>
          <div className="mt-3">
            <Autocomplete<AirportResult>
              endpoint={originsEndpoint}
              value={query}
              placeholder="Add any European airport"
              ariaLabel="Add a departure airport"
              optionKey={(airport) => airport.iataCode}
              onSelect={(airport) => {
                onAdd(airport);
                setQuery("");
              }}
              renderOption={(airport) => (
                <span className="flex items-baseline justify-between gap-4">
                  <span className="font-medium text-cloud">
                    {airport.city ?? airport.name} ({airport.iataCode})
                  </span>
                  <span className="font-mono text-[10px] uppercase text-mist">
                    {airport.countryName}
                  </span>
                </span>
              )}
            />
          </div>
          {selected.length === 0 ? (
            <p className="mt-3 font-mono text-[11px] text-gold">
              Pick at least one airport to search from.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
