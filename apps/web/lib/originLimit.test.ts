import { describe, expect, it } from "vitest";

import { canAddOrigin, originLimitMessage, type OriginLimit } from "./originLimit";

const free: OriginLimit = { max: 3, known: true, planName: "Free", canRaise: true };
const anon: OriginLimit = { max: 6, known: true, planName: null, canRaise: true };
const unknown: OriginLimit = {
  max: Number.POSITIVE_INFINITY,
  known: false,
  planName: null,
  canRaise: false,
};

describe("capping origin selection to what the plan allows", () => {
  it("allows adding below the ceiling", () => {
    expect(canAddOrigin(free, 0)).toBe(true);
    expect(canAddOrigin(free, 2)).toBe(true);
  });

  it("stops at the ceiling, because the search behind it answers 402", () => {
    expect(canAddOrigin(free, 3)).toBe(false);
  });

  it("never blocks while the limit is unknown", () => {
    // Failing to learn the limit must degrade to the old behaviour — let the
    // backend answer — rather than locking someone out of their own search.
    expect(canAddOrigin(unknown, 0)).toBe(true);
    expect(canAddOrigin(unknown, 50)).toBe(true);
  });

  it("says nothing at all while the limit is unknown", () => {
    expect(originLimitMessage(unknown, 9)).toBeNull();
  });

  it("stays quiet until the ceiling is actually reached", () => {
    expect(originLimitMessage(free, 1)).toBeNull();
    expect(originLimitMessage(free, 2)).toBeNull();
  });

  it("names the plan when the ceiling is reached", () => {
    expect(originLimitMessage(free, 3)).toContain("Free");
    expect(originLimitMessage(free, 3)).toContain("3 origin airports");
  });

  it("explains a signed-out ceiling without naming a plan", () => {
    const message = originLimitMessage(anon, 6)!;
    expect(message).toContain("Sign in");
    expect(message).not.toContain("Free");
  });

  it("tells someone over the ceiling exactly how many to remove", () => {
    // A lapsed trial can leave eight airports selected against a limit of
    // three. Silently discarding five would be a worse surprise than saying so.
    const message = originLimitMessage(free, 8)!;
    expect(message).toContain("Remove 5");
  });

  it("still allows removing when already over the ceiling", () => {
    // canAddOrigin governs adding only; the picker always permits deselection,
    // which is the only way back under the limit.
    expect(canAddOrigin(free, 8)).toBe(false);
  });

  it("uses the singular for a limit of one", () => {
    const one: OriginLimit = { max: 1, known: true, planName: "Free", canRaise: true };
    expect(originLimitMessage(one, 1)).toContain("1 origin airport");
    expect(originLimitMessage(one, 1)).not.toContain("airports");
  });
});
