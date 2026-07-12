"use client";

import { useState } from "react";

import { ApiError, apiPost } from "../lib/api";
import { Button } from "./ui/Button";
import { Notice, Spinner } from "./ui/Misc";
import type { ItineraryItem, ItineraryPlan, ItineraryResponse } from "../lib/types";

const PART_ORDER = ["morning", "afternoon", "evening", "flexible"] as const;

const PART_LABEL: Record<string, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
  flexible: "Anytime",
};

function costLabel(cost: string): string {
  const normalized = cost.trim();
  if (!normalized) return "";
  const lower = normalized.toLowerCase();
  // Costs are never exact or guaranteed — say so unless the model already did,
  // or the item is free/varies.
  if (lower === "free" || lower === "varies" || lower.includes("estimate")) return normalized;
  return `${normalized} · estimate`;
}

function DayItems({ items }: { items: ItineraryItem[] }) {
  return (
    <div className="grid gap-6 sm:grid-cols-3">
      {PART_ORDER.filter((part) => items.some((item) => item.partOfDay === part)).map((part) => (
        <div key={part}>
          <span className="mb-3 block font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
            {PART_LABEL[part]}
          </span>
          <div className="space-y-4">
            {items
              .filter((item) => item.partOfDay === part)
              .map((item, index) => (
                <div key={index}>
                  <p className="font-mono text-xs font-medium uppercase text-mist">{item.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-cloud">{item.description}</p>
                  {item.estimatedCost ? (
                    <p className="mono-num mt-1.5 font-mono text-[10px] uppercase tracking-[0.06em] text-mist/80">
                      {costLabel(item.estimatedCost)}
                    </p>
                  ) : null}
                </div>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ItineraryPlanner({
  suggestionId,
  initialPlan,
}: {
  suggestionId: string;
  initialPlan?: ItineraryPlan | null;
}) {
  const [plan, setPlan] = useState<ItineraryPlan | null>(initialPlan ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    setLoading(true);
    setError("");
    try {
      const res = await apiPost<ItineraryResponse>(`/trips/suggestions/${suggestionId}/plan`);
      setPlan(res.itinerary);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError("AI planning isn't switched on for this environment yet — check back soon.");
      } else if (err instanceof ApiError && err.status === 502) {
        setError("The planner had trouble responding. Please try again in a moment.");
      } else {
        setError("Could not build your plan. Is the API running?");
      }
    } finally {
      setLoading(false);
    }
  }

  if (!plan) {
    return (
      <section className="border-t border-line pt-10">
        <h2 className="font-display text-3xl font-medium text-cloud sm:text-4xl">Plan your days</h2>
        <p className="mt-3 max-w-xl leading-relaxed text-mist">
          A day-by-day plan tuned to how you like to travel — what to eat, where to wander, cost
          estimates — built around your exact arrival and departure times.
        </p>
        {error ? (
          <div className="mt-4">
            <Notice tone="warning">{error}</Notice>
          </div>
        ) : null}
        <div className="mt-6">
          <Button onClick={generate} disabled={loading} size="lg">
            {loading ? <Spinner label="Planning your trip…" /> : "Plan my trip"}
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="border-t border-line pt-10">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-3xl font-medium text-cloud sm:text-4xl">Your days, planned.</h2>
        <span className="font-mono text-[10px] font-semibold uppercase tracking-label text-mint">
          AI-tailored · suggestions to verify
        </span>
      </div>
      <p className="mt-3 max-w-2xl leading-relaxed text-mist">{plan.summary}</p>

      <div className="mt-10 space-y-10">
        {plan.days.map((day, index) => (
          <article key={index} className="border-l-2 border-mint/40 pl-6">
            <h3 className="font-display text-2xl font-medium text-cloud">{day.label}</h3>
            <div className="mt-5">
              <DayItems items={day.items} />
            </div>
          </article>
        ))}
      </div>

      <div className="mt-12 grid gap-8 border-t border-line pt-8 sm:grid-cols-2">
        {plan.gettingAround ? (
          <div>
            <span className="mb-3 block font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
              Getting around
            </span>
            <p className="text-sm leading-relaxed text-mist">{plan.gettingAround}</p>
          </div>
        ) : null}
        {plan.extraCostEstimate ? (
          <div>
            <span className="mb-3 block font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
              Estimated extra spend
            </span>
            <p className="mono-num text-sm leading-relaxed text-mist">{plan.extraCostEstimate}</p>
          </div>
        ) : null}
      </div>

      {plan.disclaimers.length ? (
        <ul className="mt-8 space-y-1 border-t border-line pt-5">
          {plan.disclaimers.map((disclaimer, index) => (
            <li key={index} className="font-mono text-[10px] uppercase tracking-[0.06em] text-mist/60">
              {disclaimer}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
