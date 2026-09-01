import { formatPrice } from "../lib/format";
import type { PriceHistory, TripOption } from "../lib/types";

/**
 * What Triplet's own records say about this fare.
 *
 * A distribution, not a trend line. Fare observations arrive whenever the
 * provider has priced a route, which is irregular and gappy — drawing a line
 * through them would invent movement between points that were never measured.
 * Where this fare sits among comparable ones is a question the data can
 * actually answer, so that is the question the panel asks.
 *
 * Only round trips and one-ways reach here. An open-jaw or a multi-city total is
 * assembled from separately observed legs, and comparing that against
 * single-ticket history would be comparing two different things — the backend
 * excludes them from classification rather than letting the UI decide.
 */

/**
 * Every classification the backend can produce, typed so adding one there is a
 * compile error here rather than a verdict that silently disappears.
 *
 * The dearer bands are stated as plainly as the cheaper ones. A tool that only
 * speaks up about bargains is a tool that flatters every price it shows.
 */
const CLASSIFICATION_COPY: Record<
  NonNullable<PriceHistory["classification"]>,
  { label: string; tone: string }
> = {
  exceptional: { label: "Exceptional fare", tone: "text-mint" },
  great: { label: "Great price", tone: "text-mint" },
  good: { label: "Good price", tone: "text-gold" },
  typical: { label: "Typical price", tone: "text-mist" },
  high: { label: "Above typical", tone: "text-coral" },
  very_high: { label: "Well above typical", tone: "text-coral" },
};

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[11px] uppercase tracking-label text-mist/70">{label}</dt>
      <dd className="mono-num mt-1 font-display text-lg font-bold text-cloud">{value}</dd>
    </div>
  );
}

/**
 * Where this fare sits in the observed range.
 *
 * The band is the typical range; the marker is this fare. Both are positioned
 * from real figures, and the scale is padded only enough to keep a marker at an
 * extreme from sitting on the edge.
 */
function DistributionBar({
  current,
  low,
  high,
  median,
}: {
  current: number;
  low: number;
  high: number;
  median: number;
}) {
  const min = Math.min(current, low) * 0.96;
  const max = Math.max(current, high) * 1.04;
  const span = max - min || 1;
  const pct = (value: number) => ((value - min) / span) * 100;

  return (
    <div aria-hidden className="mt-5">
      <div className="relative h-9">
        {/* Full observed extent */}
        <div className="absolute inset-x-0 top-4 h-px bg-line" />
        {/* Typical band */}
        <div
          className="absolute top-[13px] h-[3px] bg-mist/30"
          style={{ left: `${pct(low)}%`, width: `${Math.max(pct(high) - pct(low), 1)}%` }}
        />
        {/* Median */}
        <div
          className="absolute top-[9px] h-[11px] w-px bg-mist"
          style={{ left: `${pct(median)}%` }}
        />
        {/* This fare */}
        <div
          className="absolute top-[6px] h-[17px] w-[3px] bg-mint"
          style={{ left: `${pct(current)}%` }}
        />
      </div>
      {/* A legend, not an axis. Labels pinned to the bar's edges sat under
          whatever happened to be there — with a fare well below the typical
          band, the left label read as if it belonged to the marker beside it.
          The exact figures are in the list above; what the marks mean is not
          obvious anywhere else, so that is what this says. */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-label text-mist/60">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-2.5 w-[3px] bg-mint" />
          This fare
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-2.5 w-px bg-mist" />
          Median
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-[3px] w-4 bg-mist/30" />
          Typical range
        </span>
      </div>
    </div>
  );
}

export function PriceHistoryPanel({ trip }: { trip: TripOption }) {
  const history = trip.price?.history;

  // No verdict without evidence. An estimate assembled from separate legs never
  // gets one at all, and a thin sample says so rather than guessing quietly.
  if (!history?.available || history.sampleCount === 0) {
    return (
      <section className="border-t border-line pt-8">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
          Observed price history
        </h2>
        <p className="mt-3 max-w-prose text-sm leading-relaxed text-mist">
          {trip.price?.isEstimate
            ? "This total is assembled from separately observed fares, so Triplet does not compare it against single-ticket history — that would be comparing two different things."
            : "Triplet has not recorded enough comparable fares on this route yet to say whether this price is unusual."}
        </p>
      </section>
    );
  }

  const { sampleCount, medianPrice, typicalLow, typicalHigh, classification, confidence, basis } =
    history;
  const verdict =
    classification && (confidence === "medium" || confidence === "high")
      ? CLASSIFICATION_COPY[classification]
      : null;
  const canPlot =
    medianPrice != null && typicalLow != null && typicalHigh != null && typicalHigh > typicalLow;

  // One sentence carrying everything the chart shows, for anyone not seeing it.
  const spoken = [
    `This fare is ${formatPrice(trip.totalPrice)}.`,
    typicalLow != null && typicalHigh != null
      ? `Comparable fares Triplet has observed typically run ${formatPrice(typicalLow)} to ${formatPrice(typicalHigh)}.`
      : null,
    medianPrice != null ? `The median is ${formatPrice(medianPrice)}.` : null,
    `Based on ${sampleCount} comparable observation${sampleCount === 1 ? "" : "s"}.`,
    verdict ? `Triplet rates this ${verdict.label.toLowerCase()}.` : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="border-t border-line pt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
          Observed price history
        </h2>
        {verdict ? (
          <span
            className={`font-mono text-[11px] font-semibold uppercase tracking-label ${verdict.tone}`}
          >
            {verdict.label}
          </span>
        ) : null}
      </div>

      <p className="sr-only">{spoken}</p>

      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
        <Figure label="This fare" value={formatPrice(trip.totalPrice)} />
        {typicalLow != null && typicalHigh != null ? (
          <Figure
            label="Typical observed"
            value={`${formatPrice(typicalLow)}–${formatPrice(typicalHigh)}`}
          />
        ) : null}
        {medianPrice != null ? <Figure label="Median" value={formatPrice(medianPrice)} /> : null}
        <Figure label="Comparable fares" value={String(sampleCount)} />
      </dl>

      {canPlot ? (
        <DistributionBar
          current={trip.totalPrice}
          low={typicalLow!}
          high={typicalHigh!}
          median={medianPrice!}
        />
      ) : null}

      <p className="mt-4 max-w-prose text-xs leading-relaxed text-mist/70">
        Based on {sampleCount} comparable fare{sampleCount === 1 ? "" : "s"} Triplet has recorded
        {basis ? ` for ${basis}` : ""}. These are prices Triplet has seen, not a forecast — they say
        what this route has cost, not what it will.
        {!verdict
          ? " There are too few for Triplet to call this price unusual either way."
          : ""}
      </p>
    </section>
  );
}
