"use client";

import { useState } from "react";

import { ApiError, apiPost } from "../lib/api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { Notice, Spinner } from "./ui/Misc";
import type { ItineraryPlan, ItineraryResponse } from "../lib/types";

const PART_OF_DAY_LABEL: Record<string, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
  flexible: "Anytime",
};

const CATEGORY_ICON: Record<string, string> = {
  food: "🍽",
  nature: "🥾",
  hike: "🥾",
  culture: "🏛",
  museum: "🏛",
  transfer: "🚆",
  transport: "🚆",
  nightlife: "🌙",
  beach: "🏖",
  shopping: "🛍",
  general: "📍",
};

function iconFor(category: string): string {
  return CATEGORY_ICON[category.toLowerCase()] ?? "📍";
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
      <Card>
        <h2 className="font-display text-lg font-bold text-cloud">Plan your days</h2>
        <p className="mt-2 text-sm text-mist">
          Get a personalised, day-by-day plan tailored to your travel style — what to eat, where to
          wander, and cost estimates — built around your exact arrival and departure times.
        </p>
        {error ? (
          <div className="mt-3">
            <Notice tone="warning">{error}</Notice>
          </div>
        ) : null}
        <div className="mt-4">
          <Button onClick={generate} disabled={loading}>
            {loading ? <Spinner label="Planning your trip…" /> : "✨ Plan my trip"}
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-display text-lg font-bold text-cloud">Your day-by-day plan</h2>
        <span className="rounded-full bg-mint/10 px-2.5 py-1 text-[11px] font-semibold text-mint">
          AI-tailored
        </span>
      </div>
      <p className="mt-2 text-sm text-mist">{plan.summary}</p>

      <div className="mt-5 space-y-5">
        {plan.days.map((day, i) => (
          <div key={i} className="border-l-2 border-mint/30 pl-4">
            <h3 className="font-display text-base font-semibold text-cloud">{day.label}</h3>
            <ul className="mt-2 space-y-3">
              {day.items.map((item, j) => (
                <li key={j} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span aria-hidden>{iconFor(item.category)}</span>
                    <span className="font-semibold text-cloud">{item.title}</span>
                    <span className="text-[11px] uppercase tracking-wide text-mist/70">
                      {PART_OF_DAY_LABEL[item.partOfDay] ?? item.partOfDay}
                    </span>
                  </div>
                  <p className="mt-1 text-mist">{item.description}</p>
                  {item.estimatedCost ? (
                    <p className="mt-1 text-xs text-mist/80">Est. cost: {item.estimatedCost}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {plan.gettingAround ? (
        <div className="mt-5 rounded-xl bg-white/[0.03] px-4 py-3 text-sm">
          <p className="font-semibold text-cloud">Getting around</p>
          <p className="mt-1 text-mist">{plan.gettingAround}</p>
        </div>
      ) : null}

      {plan.extraCostEstimate ? (
        <div className="mt-3 rounded-xl bg-white/[0.03] px-4 py-3 text-sm">
          <p className="font-semibold text-cloud">Estimated extra spend</p>
          <p className="mt-1 text-mist">{plan.extraCostEstimate}</p>
        </div>
      ) : null}

      {plan.disclaimers.length ? (
        <ul className="mt-4 space-y-1 text-xs text-mist/70">
          {plan.disclaimers.map((d, i) => (
            <li key={i}>• {d}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
