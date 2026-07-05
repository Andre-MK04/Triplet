"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { useAuth } from "../../../components/AuthContext";
import { TripCard } from "../../../components/TripCard";
import { ButtonLink } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { EmptyState, Notice, Spinner } from "../../../components/ui/Misc";
import { ApiError, apiGet } from "../../../lib/api";
import { formatDateLong, timeAgo } from "../../../lib/format";
import type { TripSuggestionResponse } from "../../../lib/types";

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
          icon="🕰"
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

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-5 pb-10">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-mint">Trip suggestion</p>
          <h1 className="mt-1 font-display text-3xl font-bold text-cloud">{suggestion!.title}</h1>
          <p className="mt-1 text-sm text-mist">
            Suggested {observed ?? formatDateLong(suggestion!.createdAt)}
            {suggestion!.expiresAt ? ` · link expires ${formatDateLong(suggestion!.expiresAt)}` : ""}
          </p>
        </header>

        <Notice tone="info">{suggestion!.disclaimer}</Notice>

        <TripCard trip={{ ...trip, suggestionId: null }} />

        <Card>
          <h2 className="font-display text-lg font-bold text-cloud">Before you book</h2>
          <ul className="mt-3 space-y-2 text-sm text-mist">
            <li>• This trip is built from independent one-way fares — book both legs yourself.</li>
            {trip.tripType === "open_jaw" ? (
              <li>• It includes a ground transfer between cities; check timetables before buying flights.</li>
            ) : null}
            <li>• Fares were observed when this suggestion was created and are not guaranteed.</li>
            <li>• Always check the final price with the airline or provider before paying.</li>
          </ul>
        </Card>

        <div className="flex justify-center">
          <ButtonLink href="/discover" variant="secondary">← Back to Discover</ButtonLink>
        </div>
      </div>
    </AppShell>
  );
}
