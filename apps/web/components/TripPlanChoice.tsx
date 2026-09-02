"use client";

import type { TripPlan } from "../lib/types";

type Option = {
  value: TripPlan;
  label: string;
  hint: string;
};

// Return is deliberately first and default: most trips are out and back, and a
// traveller who wants more has to say so rather than be talked into it.
const OPTIONS: Option[] = [
  { value: "return", label: "Return", hint: "Out and back from one city" },
  { value: "multi_city", label: "Multi-city", hint: "Fly between several cities in order" },
  { value: "open_jaw", label: "Open-jaw", hint: "Fly in to one city, home from another" },
];

export function TripPlanChoice({
  value,
  onChange,
}: {
  value: TripPlan;
  onChange: (plan: TripPlan) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2.5 font-mono text-[10px] font-semibold uppercase tracking-label text-mist">
        Trip shape
      </legend>
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        {OPTIONS.map((option) => {
          const selected = value === option.value;
          return (
            <label
              key={option.value}
              className="group flex cursor-pointer items-start gap-2.5"
              title={option.hint}
            >
              <input
                type="radio"
                name="trip-plan"
                value={option.value}
                checked={selected}
                onChange={() => onChange(option.value)}
                className="peer sr-only"
              />
              <span
                aria-hidden
                className={
                  "mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border transition-colors " +
                  "peer-focus-visible:ring-2 peer-focus-visible:ring-mint peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-ink " +
                  (selected ? "border-mint" : "border-line group-hover:border-mint/50")
                }
              >
                <span
                  className={
                    "h-2 w-2 rounded-full transition-transform " +
                    (selected ? "scale-100 bg-mint" : "scale-0 bg-transparent")
                  }
                />
              </span>
              <span className="min-w-0">
                <span
                  className={
                    "block text-sm font-medium leading-tight transition-colors " +
                    (selected ? "text-cloud" : "text-mist group-hover:text-cloud")
                  }
                >
                  {option.label}
                </span>
                <span className="mt-0.5 block text-xs leading-tight text-mist-dim">{option.hint}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
