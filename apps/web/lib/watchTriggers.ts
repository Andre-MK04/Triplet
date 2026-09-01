/**
 * What makes a watch worth an email.
 *
 * A separate question from how often Triplet checks, and they are presented
 * separately: merging them is why "tell me less often" used to also mean "tell
 * me about less", which is not the same wish at all.
 *
 * Only the four the alert runner actually implements are offered. A fifth
 * option the backend silently ignored would be worse than no choice — the
 * traveller would believe they had set something.
 */
export type WatchTriggerMode = "any" | "below_budget" | "route_deal" | "price_drop";

export const WATCH_TRIGGERS: {
  value: WatchTriggerMode;
  label: string;
  hint: string;
}[] = [
  {
    value: "any",
    label: "Any trip worth seeing",
    hint: "Anything matching this search, once the price improves on what you were last told.",
  },
  {
    value: "below_budget",
    label: "It comes in under my budget",
    hint: "Only when a matching trip costs less than your ceiling — and only when it beats the last one you heard about.",
  },
  {
    value: "route_deal",
    label: "It's unusually cheap for this route",
    hint: "Measured against what Triplet has seen this search cost before, so a route that is always cheap does not keep announcing itself.",
  },
  {
    value: "price_drop",
    label: "The price drops meaningfully",
    hint: "Only on a real fall from the last price Triplet told you about — a euro off is not news.",
  },
];

export function triggerHint(mode: WatchTriggerMode): string {
  return WATCH_TRIGGERS.find((trigger) => trigger.value === mode)?.hint ?? "";
}
