"use client";

import Link from "next/link";

import type { OpportunityFeed } from "../lib/types";
import { TripRow } from "./TripRow";

export function OpportunityRail({
  feed,
  status,
  compact = false,
}: {
  feed: OpportunityFeed | null;
  status: "idle" | "loading" | "ready" | "error";
  compact?: boolean;
}) {
  if (status === "idle") return null;

  return (
    <section aria-labelledby="opportunity-heading" className="border-t border-line py-10 sm:py-14">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint">From your airports</p>
          <h2 id="opportunity-heading" className="mt-2 font-display text-3xl font-bold text-cloud sm:text-4xl">
            Look where you could go.
          </h2>
          {feed?.originAirports.length ? (
            <p className="mt-2 text-sm text-mist">
              Observed returns from {feed.originAirports.join(" · ")}. Prices can change when you check.
            </p>
          ) : null}
        </div>
        <Link href="/discover" className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint hover:text-cloud">
          Shape a search ↗
        </Link>
      </div>

      {status === "loading" ? (
        <div aria-live="polite" className="border-y border-line py-9 text-sm text-mist">Checking your observed fare board…</div>
      ) : null}
      {status === "error" ? (
        <div className="border-y border-line py-8 text-sm text-mist">
          Your fare board could not load. You can still <Link href="/discover" className="text-mint underline">search trips</Link>.
        </div>
      ) : null}
      {status === "ready" && feed?.originAirports.length === 0 ? (
        <div className="border-y border-line py-8 text-sm text-mist">
          Choose departure airports in your <Link href="/onboarding" className="text-mint underline">travel profile</Link> to get your own fare board.
        </div>
      ) : null}
      {status === "ready" && feed?.originAirports.length && feed.trips.length === 0 ? (
        <div className="border-y border-line py-8 text-sm text-mist">
          No usable observed return fares are in the cache for these airports yet. A structured search can check more routes and dates.
        </div>
      ) : null}
      {status === "ready" && feed?.trips.length ? (
        <>
          {feed.isStale ? (
            <p className="mb-4 border-l-2 border-gold/50 pl-3 text-xs text-mist">
              Some fare sightings are older. Each row shows its own observation time; check the current price with the provider.
            </p>
          ) : null}
          <div className="border-t border-line">
            {(compact ? feed.trips.slice(0, 4) : feed.trips).map((trip) => (
              <TripRow key={trip.id} trip={trip} />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
