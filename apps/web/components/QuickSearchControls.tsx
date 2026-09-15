"use client";

type QuickSearchValue = {
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  travelStyles: string[];
};

function after(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={
        "min-h-11 border px-3 py-2 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-mint " +
        (selected ? "border-mint bg-mint/10 text-cloud" : "border-line text-mist hover:border-mint/50 hover:text-cloud")
      }
    >
      {children}
    </button>
  );
}

export function QuickSearchControls({
  value,
  onChange,
}: {
  value: QuickSearchValue;
  onChange: (changes: Partial<QuickSearchValue>) => void;
}) {
  const windows = [
    { label: "Soon", start: after(7), end: after(45) },
    { label: "Next 3 months", start: after(21), end: after(90) },
    { label: "Flexible", start: after(7), end: after(270) },
  ];
  const lengths = [
    { label: "2–3 nights", min: 2, max: 3 },
    { label: "4–7 nights", min: 4, max: 7 },
    { label: "8–14 nights", min: 8, max: 14 },
  ];
  const moods = [
    { label: "Beach", key: "beach" },
    { label: "Food", key: "food" },
    { label: "Nature", key: "nature" },
    { label: "Culture", key: "culture" },
    { label: "Adventure", key: "cheap_adventure" },
  ];

  return (
    <div className="grid gap-5 border-t border-line pt-5 sm:grid-cols-2">
      <fieldset>
        <legend className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">When?</legend>
        <div className="flex flex-wrap gap-2">
          {windows.map((window) => (
            <Choice key={window.label} selected={value.startDate === window.start && value.endDate === window.end}
              onClick={() => onChange({ startDate: window.start, endDate: window.end })}>
              {window.label}
            </Choice>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">Flight budget?</legend>
        <div className="flex flex-wrap gap-2">
          {[100, 200, 400, 5000].map((amount) => (
            <Choice key={amount} selected={value.maxBudget === amount} onClick={() => onChange({ maxBudget: amount })}>
              {amount === 5000 ? "No firm cap" : `Under €${amount}`}
            </Choice>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">How long?</legend>
        <div className="flex flex-wrap gap-2">
          {lengths.map((length) => (
            <Choice key={length.label} selected={value.minTripLengthDays === length.min && value.maxTripLengthDays === length.max}
              onClick={() => onChange({ minTripLengthDays: length.min, maxTripLengthDays: length.max })}>
              {length.label}
            </Choice>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">What feels right?</legend>
        <div className="flex flex-wrap gap-2">
          {moods.map((mood) => (
            <Choice key={mood.key} selected={value.travelStyles.includes(mood.key)} onClick={() =>
              onChange({ travelStyles: value.travelStyles.includes(mood.key)
                ? value.travelStyles.filter((key) => key !== mood.key)
                : [...value.travelStyles, mood.key] })}>
              {mood.label}
            </Choice>
          ))}
        </div>
        <p className="mt-2 text-xs text-mist-dim">These rank destinations; they do not claim actual weather.</p>
      </fieldset>
    </div>
  );
}
