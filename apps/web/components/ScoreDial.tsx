const TONES = {
  gold: "#ffd08a",
  mint: "#7ddfc3",
} as const;

type ScoreDialProps = {
  value: number;
  tone?: keyof typeof TONES;
  /** Diameter in px. The ring stays thin regardless of size. */
  size?: number;
  label?: string;
};

/**
 * Thin-ring gauge for DealScore (gold) and FitScore (mint) — one of the two
 * permitted circular shapes in the design system.
 */
export function ScoreDial({ value, tone = "gold", size = 40, label }: ScoreDialProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const color = TONES[tone];

  return (
    <span className="inline-flex flex-col items-center gap-1">
      <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden>
          <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(232, 240, 244, 0.12)" strokeWidth="5" />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="5"
            strokeDasharray={`${(clamped / 100) * circumference} ${circumference}`}
            transform="rotate(-90 50 50)"
          />
        </svg>
        <span
          className="mono-num absolute font-mono font-medium"
          style={{ color, fontSize: Math.max(10, size * 0.3) }}
        >
          {clamped}
        </span>
      </span>
      {label ? (
        <span className="font-mono text-[9px] uppercase tracking-label text-mist">{label}</span>
      ) : null}
    </span>
  );
}
