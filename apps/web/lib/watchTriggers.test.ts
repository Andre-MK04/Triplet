import { describe, expect, it } from "vitest";

import { WATCH_TRIGGERS, triggerHint, type WatchTriggerMode } from "./watchTriggers";

/**
 * The trigger choices offered to travellers.
 *
 * The rule worth enforcing is that this list never drifts ahead of the alert
 * runner. An option the backend silently ignores is worse than no option: the
 * traveller believes they have set something, and the watch behaves as though
 * they had not.
 */

/** Exactly the modes app/alerts/schemas.py accepts and _should_notify implements. */
const BACKEND_MODES: WatchTriggerMode[] = ["any", "below_budget", "route_deal", "price_drop"];

describe("offered triggers", () => {
  it("offers every mode the runner implements and no others", () => {
    expect(WATCH_TRIGGERS.map((t) => t.value).sort()).toEqual([...BACKEND_MODES].sort());
  });

  it("leads with the least restrictive option", () => {
    // "Any trip worth seeing" is the default and the safest starting point:
    // someone who has not thought about triggers should not get silence.
    expect(WATCH_TRIGGERS[0].value).toBe("any");
  });

  it("explains what each one actually means", () => {
    // The labels are short enough to be ambiguous; the hint is what decides
    // whether a watch turns out useful or a source of noise.
    for (const trigger of WATCH_TRIGGERS) {
      expect(trigger.hint.length, `${trigger.value} has no usable hint`).toBeGreaterThan(30);
      expect(trigger.label.length).toBeGreaterThan(0);
    }
  });

  it("describes triggers in plain language, not backend vocabulary", () => {
    for (const trigger of WATCH_TRIGGERS) {
      expect(trigger.label).not.toMatch(/_/);
      expect(trigger.label.toLowerCase()).not.toContain("mode");
    }
  });

  it("returns a hint for every mode and nothing for an unknown one", () => {
    for (const mode of BACKEND_MODES) {
      expect(triggerHint(mode)).toBeTruthy();
    }
    expect(triggerHint("not_a_mode" as WatchTriggerMode)).toBe("");
  });
});
