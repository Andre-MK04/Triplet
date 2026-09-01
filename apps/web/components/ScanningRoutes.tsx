/**
 * The waiting state for a search.
 *
 * A route being drawn rather than a spinner: a search takes long enough that
 * the wait is worth explaining, and the caption says what Triplet is doing
 * rather than only that it is busy.
 */
export function ScanningRoutes() {
  return (
    <div className="flex flex-col items-center gap-4 border-y border-line px-6 py-16 text-center" role="status">
      <svg viewBox="0 0 200 60" className="h-14 w-56" aria-hidden>
        <path d="M10 45 Q 100 -10 190 40" fill="none" stroke="rgba(232,240,244,0.15)" strokeWidth="2" />
        <path d="M10 45 Q 100 -10 190 40" fill="none" stroke="#7ddfc3" strokeWidth="2" className="route-line" />
        <circle cx="10" cy="45" r="4" fill="#7ddfc3" />
        <circle cx="190" cy="40" r="4" fill="#ff9a78" />
      </svg>
      <p className="font-mono text-[11px] uppercase tracking-label text-mist">
        Scanning fares · pairing outbound and return legs
      </p>
    </div>
  );
}
