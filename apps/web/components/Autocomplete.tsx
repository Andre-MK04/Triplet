"use client";

import { useEffect, useRef, useState } from "react";

import { apiGet } from "../lib/api";

type AutocompleteProps<T> = {
  /** Builds the request path from the (already-encoded) query. */
  endpoint: (query: string) => string;
  placeholder?: string;
  minChars?: number;
  ariaLabel?: string;
  renderOption: (item: T) => React.ReactNode;
  optionKey: (item: T) => string;
  onSelect: (item: T) => void;
  /** Text shown in the input after a selection (controlled by the parent). */
  value?: string;
};

/**
 * Debounced type-ahead over a GET endpoint returning a JSON array. Handles the
 * loading / empty / error states the design calls for, keyboard nav, and blur.
 */
export function Autocomplete<T>({
  endpoint,
  placeholder,
  minChars = 2,
  ariaLabel,
  renderOption,
  optionKey,
  onSelect,
  value,
}: AutocompleteProps<T>) {
  const [query, setQuery] = useState(value ?? "");
  const [results, setResults] = useState<T[]>([]);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [highlight, setHighlight] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value !== undefined) setQuery(value);
  }, [value]);

  useEffect(() => {
    const term = query.trim();
    if (term.length < minChars) {
      setResults([]);
      setStatus("idle");
      return;
    }
    let cancelled = false;
    setStatus("loading");
    const timer = setTimeout(() => {
      apiGet<T[]>(endpoint(encodeURIComponent(term)))
        .then((data) => {
          if (cancelled) return;
          setResults(data);
          setStatus("idle");
          setHighlight(0);
          setOpen(true);
        })
        .catch(() => {
          if (cancelled) return;
          setStatus("error");
          setResults([]);
        });
    }, 220);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, endpoint, minChars]);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function choose(item: T) {
    onSelect(item);
    setOpen(false);
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (!open || results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => Math.min(h + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(results[highlight]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const term = query.trim();
  return (
    <div ref={boxRef} className="relative">
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => results.length && setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-label={ariaLabel}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        className="cmd-input w-full py-2.5 font-mono text-sm text-cloud placeholder:text-mist/50"
      />
      {open ? (
        <div className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto border border-line bg-ink-raised">
          {status === "loading" ? (
            <p className="px-4 py-3 font-mono text-[11px] uppercase tracking-label text-mist">Searching…</p>
          ) : status === "error" ? (
            <p className="px-4 py-3 font-mono text-[11px] uppercase tracking-label text-coral">
              Couldn&apos;t reach search. Try again.
            </p>
          ) : results.length === 0 && term.length >= minChars ? (
            <p className="px-4 py-3 font-mono text-[11px] uppercase tracking-label text-mist">
              No matches for “{term}”
            </p>
          ) : (
            results.map((item, index) => (
              <button
                key={optionKey(item)}
                type="button"
                onMouseEnter={() => setHighlight(index)}
                onClick={() => choose(item)}
                className={
                  "block w-full border-b border-line px-4 py-2.5 text-left text-sm last:border-b-0 transition-colors " +
                  (index === highlight ? "bg-mint/10 text-cloud" : "text-mist hover:bg-mint/5")
                }
              >
                {renderOption(item)}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
