"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { useAuth } from "../../../components/AuthContext";
import { BoardingPass } from "../../../components/BoardingPass";
import { ItineraryPlanner } from "../../../components/ItineraryPlanner";
import { ScoreDial } from "../../../components/ScoreDial";
import { ButtonLink } from "../../../components/ui/Button";
import { EmptyState, Spinner } from "../../../components/ui/Misc";
import { ApiError, apiGet } from "../../../lib/api";
import { airportCity } from "../../../lib/airports";
import { formatDateLong, timeAgo } from "../../../lib/format";
import type { TripSuggestionResponse } from "../../../lib/types";

const NIGHT_WORDS = [
  "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
];

function nightsPhrase(nights: number): string {
  const word = NIGHT_WORDS[nights] ?? String(nights);
  return `${word} night${nights === 1 ? "" : "s"}`;
}

export function TripDetailClient({ suggestionId }: { suggestionId: string }) {
  const { isLoading: authLoading } = useAuth();
  const [suggestion, setSuggestion] = useState<TripSuggestionResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;
    apiGet<TripSuggestionResponse>(`/trips/suggestions/${suggestionId}`)
      .then(setSuggestion)
      .catch((loadError) => {
        setError(
          loadError instanceof ApiError && loadError.status === 404
            ? "This trip suggestion doesn't exist, has expired, or belongs to another account."
            : "Could not load this trip. Is the API running?",
        );
      });
  }, [suggestionId, authLoading]);

  if (!suggestion && !error) {
    return (
      <AppShell>
        <div className="flex justify-center py-24"><Spinner label="Loading trip…" /></div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <EmptyState
          title="Trip not found"
          action={<ButtonLink href="/discover">Search fresh trips</ButtonLink>}
        >
          {error}
        </EmptyState>
      </AppShell>
    );
  }

  const trip = suggestion!.trip;
  const observed = timeAgo(suggestion!.createdAt);
  const isOpenJaw = trip.tripType === "open_jaw";
  const destCity = airportCity(trip.outboundFlight.destination);
  const returnCity = airportCity(trip.returnFlight.origin);
  const headline = isOpenJaw
    ? `${destCity} & ${returnCity}, ${nightsPhrase(trip.nights)}.`
    : `${destCity}, ${nightsPhrase(trip.nights)}.`;

  const beforeYouBook = [
    trip.fareKind === "round_trip_bundle"
      ? "This is a single round-trip fare — book it as one ticket with the airline or agent."
      : "Fares are independent one-ways — you book each leg yourself, directly with the airline.",
    "Prices were observed when this suggestion was created and can change at checkout — always verify the final fare.",
    ...(isOpenJaw
      ? ["This trip includes a ground transfer between cities — check timetables before buying flights."]
      : []),
    ...trip.warnings,
  ];

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-10 pb-16">
        <header>
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
            Trip suggestion
          </p>
          <h1 className="font-display text-4xl font-bold tracking-tight text-cloud sm:text-5xl">{headline}</h1>
          <p className="mt-3 font-mono text-[10px] uppercase tracking-label text-mist/70">
            Priced {observed ?? formatDateLong(suggestion!.createdAt)}
            {suggestion!.expiresAt ? ` · link expires ${formatDateLong(suggestion!.expiresAt)}` : ""}
          </p>
        </header>

        <BoardingPass trip={trip} />

        {/* Scores with plain-English explanations */}
        <section className="grid gap-8 sm:grid-cols-2">
          <div className="flex items-start gap-5">
            <ScoreDial value={suggestion!.dealScore} tone="gold" size={80} />
            <div>
              <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-gold">
                Deal score
              </span>
              <p className="mt-1.5 max-w-xs text-sm leading-relaxed text-mist">
                {trip.explanation ||
                  "How this fare compares against the price history we've observed on this route."}
              </p>
            </div>
          </div>
          {suggestion!.fitScore != null ? (
            <div className="flex items-start gap-5">
              <ScoreDial value={suggestion!.fitScore} tone="mint" size={80} />
              <div>
                <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
                  Fit score
                </span>
                <p className="mt-1.5 max-w-xs text-sm leading-relaxed text-mist">
                  How well this trip matches your travel profile — airports, trip length, style and
                  comfort rules.
                </p>
              </div>
            </div>
          ) : null}
        </section>

        {/* Before you book */}
        <section className="border-t border-line pt-8">
          <span className="mb-5 block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Before you book
          </span>
          <ol className="space-y-3">
            {beforeYouBook.map((item, index) => (
              <li key={item} className="flex gap-4">
                <span className="mono-num pt-0.5 font-mono text-[10px] text-mint">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <p className="font-mono text-[11px] uppercase leading-relaxed tracking-[0.04em] text-mist">
                  {item}
                </p>
              </li>
            ))}
          </ol>
        </section>

        <ItineraryPlanner suggestionId={suggestion!.id} initialPlan={suggestion!.itinerary} />

        <div className="flex justify-center border-t border-line pt-8">
          <ButtonLink href="/discover" variant="secondary">← Back to Discover</ButtonLink>
        </div>
      </div>
    </AppShell>
  );
}
