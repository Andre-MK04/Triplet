"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Hand this search to someone else.
 *
 * The URL already describes the search, so this is only about getting it into
 * a person's hands without asking them to select the address bar. The native
 * share sheet where there is one, the clipboard everywhere else, and — because
 * both can be unavailable or refused — the raw link on screen as a last resort,
 * so the answer is never "it didn't work, and here is nothing".
 */
export function ShareSearch({ url, className = "" }: { url: string; className?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "manual">("idle");
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );

  function settle(next: "copied" | "manual") {
    setState(next);
    if (timer.current) window.clearTimeout(timer.current);
    // Long enough to read, short enough not to become part of the furniture.
    timer.current = window.setTimeout(() => setState("idle"), next === "copied" ? 2600 : 12000);
  }

  async function share() {
    // The share sheet first on the devices that have one: it reaches the apps
    // people actually send links through.
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title: "A trip search on Triplet", url });
        return;
      } catch (error) {
        // A cancelled share sheet is a decision, not a failure — do not fall
        // through to the clipboard and act as though something happened.
        if (error instanceof DOMException && error.name === "AbortError") return;
      }
    }

    try {
      await navigator.clipboard.writeText(url);
      settle("copied");
    } catch {
      // Clipboard access is refused in plenty of ordinary situations — an
      // insecure origin, a permission prompt declined. Show the link instead.
      settle("manual");
    }
  }

  return (
    <div className={`flex flex-col items-start gap-2 ${className}`}>
      <button
        type="button"
        onClick={share}
        className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist transition-colors hover:text-mint focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint"
      >
        Share search
      </button>

      {/* Announced, because for anyone not watching this corner of the screen
          a silent state change is no feedback at all. */}
      <p className="text-xs text-mint" role="status">
        {state === "copied" ? "Search link copied" : null}
      </p>

      {state === "manual" ? (
        <label className="flex w-full max-w-md flex-col gap-1">
          <span className="font-mono text-[10px] uppercase tracking-label text-mist-dim">
            Copy this link
          </span>
          <input
            readOnly
            value={url}
            onFocus={(event) => event.currentTarget.select()}
            className="w-full border border-line bg-ink-soft px-2 py-1.5 font-mono text-xs text-cloud"
          />
        </label>
      ) : null}
    </div>
  );
}
