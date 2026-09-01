"use client";

import { useEffect, useState } from "react";

import { apiPost } from "../lib/api";
import { formatPrice } from "../lib/format";
import {
  fareCheckToAsk,
  forgetAllFareChecks,
  settleFareCheck,
  type FareCheckResponse,
  type PendingFareCheck,
} from "../lib/fareCheck";

/**
 * "Was the live price still close?"
 *
 * The one question only a traveller can answer: Triplet shows observed fares
 * and cannot see what the provider showed when they arrived. Asked at most once
 * a day, about one fare, and never twice about the same one.
 *
 * No exact figure is requested. Asking someone to transcribe a price from
 * another site produces guesses, and a band is what the question needs — how
 * far observed fares drift by age, not what one fare cost to the cent.
 */

const OPTIONS: { value: FareCheckResponse; label: string }[] = [
  { value: "matched", label: "About the same" },
  { value: "slightly_higher", label: "A little higher" },
  { value: "much_higher", label: "Much higher" },
  { value: "unavailable", label: "No longer available" },
];

export function FareCheckPrompt() {
  const [check, setCheck] = useState<PendingFareCheck | null>(null);
  const [answered, setAnswered] = useState(false);

  useEffect(() => {
    // Read after mount: this depends on localStorage, and deciding on the
    // server would render a prompt the browser then disagrees with.
    setCheck(fareCheckToAsk());
  }, []);

  if (!check) return null;

  async function answer(response: FareCheckResponse) {
    if (!check) return;
    settleFareCheck(check.checkId);
    setAnswered(true);
    try {
      await apiPost("/fare-feedback", {
        checkId: check.checkId,
        origin: check.origin,
        destination: check.destination,
        tripType: check.tripType,
        fareKind: check.fareKind,
        fareAgeBucket: check.fareAgeBucket,
        shownPrice: check.shownPrice,
        response,
        currency: check.currency,
        provider: check.provider ?? undefined,
      });
    } catch {
      // Already settled locally, so this is never asked again either way. A
      // lost answer is a lost data point, not a problem for the traveller.
    }
  }

  function dismiss() {
    if (!check) return;
    settleFareCheck(check.checkId);
    setCheck(null);
  }

  if (answered) {
    return (
      <section className="border-y border-line py-4" aria-live="polite">
        <p className="text-sm text-mist">
          Thank you — that helps Triplet judge how far observed fares drift.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="fare-check-heading" className="border-y border-line py-4">
      <h2
        id="fare-check-heading"
        className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist"
      >
        One quick question
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-cloud">
        You checked {check.destinationCity} at {formatPrice(check.shownPrice, check.currency)}. Was
        the price you found still close?
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => void answer(option.value)}
            className="border border-line px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-label text-mist transition-colors hover:border-mint hover:text-mint"
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1">
        <button
          type="button"
          onClick={dismiss}
          className="text-xs text-mist/70 underline transition-colors hover:text-cloud"
        >
          Skip
        </button>
        <button
          type="button"
          onClick={() => {
            forgetAllFareChecks();
            setCheck(null);
          }}
          className="text-xs text-mist/70 underline transition-colors hover:text-cloud"
        >
          Don&apos;t ask again
        </button>
      </div>
    </section>
  );
}
