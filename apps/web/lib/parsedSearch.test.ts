import { describe, expect, it } from "vitest";

import { MAX_BUDGET_CEILING, parsedChips } from "./parsedSearch";
import type { TripSearchPayload } from "./types";

/**
 * What the AI understood, made checkable.
 *
 * The failure these chips exist to catch is a quiet misreading — "next October"
 * taken as this October — whose only other symptom is results that feel subtly
 * wrong. So the chips must describe the search that actually ran, and must not
 * offer to drop anything a search cannot do without.
 */

function payload(overrides: Partial<TripSearchPayload> = {}): TripSearchPayload {
  return {
    originAirports: ["VIE"],
    destinationAirports: null,
    destinationCountries: [],
    destinationRegions: [],
    destinationContinents: [],
    excludeEurope: false,
    unvisitedOnly: false,
    startDate: "2026-10-01",
    endDate: "2026-10-31",
    minTripLengthDays: 8,
    maxTripLengthDays: 12,
    maxBudget: 900,
    maxGroundTransferHours: 4,
    tripStyle: "surprise me",
    tripPlan: "return",
    directOnly: false,
    ...overrides,
  } as TripSearchPayload;
}

function chip(chips: ReturnType<typeof parsedChips>, key: string) {
  return chips.find((c) => c.key === key);
}

describe("chips describe the parsed search", () => {
  it("renders nothing without a parse", () => {
    expect(parsedChips(null)).toEqual([]);
    expect(parsedChips(undefined)).toEqual([]);
  });

  it("names origin cities rather than showing codes", () => {
    const chips = parsedChips(payload({ originAirports: ["VIE", "BUD"] }));

    expect(chip(chips, "from")!.value).toContain("Vienna");
    expect(chip(chips, "from")!.value).toContain("Budapest");
  });

  it("summarises a long origin list instead of listing all of it", () => {
    const chips = parsedChips(
      payload({ originAirports: ["VIE", "BUD", "ZAG", "TRS", "VCE", "LJU"] }),
    );

    expect(chip(chips, "from")!.value).toMatch(/\+3$/);
  });

  it("turns a country code into a country name", () => {
    const chips = parsedChips(payload({ destinationCountries: ["JP"] }));

    expect(chip(chips, "destination")!.value).toBe("Japan");
  });

  it("titles a region", () => {
    const chips = parsedChips(payload({ destinationRegions: ["scandinavia"] }));

    expect(chip(chips, "destination")!.value).toBe("Scandinavia");
  });

  it("says Anywhere when no destination was understood", () => {
    const chips = parsedChips(payload());

    expect(chip(chips, "destination")!.value).toBe("Anywhere");
  });

  it("describes a single-month window as that month", () => {
    const chips = parsedChips(payload({ startDate: "2026-10-01", endDate: "2026-10-31" }));

    expect(chip(chips, "when")!.value).toBe("October");
  });

  it("describes a two-month window as a span", () => {
    const chips = parsedChips(payload({ startDate: "2026-10-01", endDate: "2026-11-20" }));

    expect(chip(chips, "when")!.value).toBe("October–November");
  });

  it("includes the year when a window crosses one", () => {
    const chips = parsedChips(payload({ startDate: "2026-12-01", endDate: "2027-01-20" }));

    expect(chip(chips, "when")!.value).toContain("2026");
    expect(chip(chips, "when")!.value).toContain("2027");
  });

  it("shows a trip length range, and a single figure when both ends agree", () => {
    expect(chip(parsedChips(payload()), "length")!.value).toBe("8–12 days");
    expect(
      chip(parsedChips(payload({ minTripLengthDays: 7, maxTripLengthDays: 7 })), "length")!.value,
    ).toBe("7 days");
  });

  it("shows the budget as a ceiling", () => {
    expect(chip(parsedChips(payload()), "budget")!.value).toContain("≤");
    expect(chip(parsedChips(payload()), "budget")!.value).toContain("900");
  });

  it("names the trip shape in the interface's own words", () => {
    expect(chip(parsedChips(payload({ tripPlan: "multi_city" })), "plan")!.value).toBe("Multi-city");
    expect(chip(parsedChips(payload({ tripPlan: "open_jaw" })), "plan")!.value).toBe("Open-jaw");
  });

  it("mentions optional constraints only when they were understood", () => {
    const plain = parsedChips(payload());
    expect(chip(plain, "direct")).toBeUndefined();
    expect(chip(plain, "outsideEurope")).toBeUndefined();
    expect(chip(plain, "unvisited")).toBeUndefined();

    const constrained = parsedChips(
      payload({ directOnly: true, excludeEurope: true, unvisitedOnly: true }),
    );
    expect(chip(constrained, "direct")).toBeDefined();
    expect(chip(constrained, "outsideEurope")).toBeDefined();
    expect(chip(constrained, "unvisited")).toBeDefined();
  });
});

describe("what may be dropped", () => {
  it("never offers to remove what a search cannot run without", () => {
    const chips = parsedChips(payload({ destinationCountries: ["JP"], directOnly: true }));

    for (const key of ["from", "when", "length", "plan"]) {
      expect(chip(chips, key)!.removable).toBe(false);
    }
  });

  it("offers to widen the constraints that meaningfully narrow a search", () => {
    const chips = parsedChips(
      payload({ destinationCountries: ["JP"], directOnly: true, excludeEurope: true }),
    );

    expect(chip(chips, "destination")!.removable).toBe(true);
    expect(chip(chips, "budget")!.removable).toBe(true);
    expect(chip(chips, "direct")!.removable).toBe(true);
    expect(chip(chips, "outsideEurope")!.removable).toBe(true);
  });

  it("does not offer to remove a destination that was never set", () => {
    // "Anywhere" is already the widest search; removing it would do nothing.
    expect(chip(parsedChips(payload()), "destination")!.removable).toBe(false);
  });

  it("explains what each removal does", () => {
    const chips = parsedChips(payload({ destinationCountries: ["JP"] }));

    for (const c of chips.filter((c) => c.removable)) {
      expect(c.removeHint, `${c.key} has no hint`).toBeTruthy();
    }
  });
});

describe("no internal parser detail leaks", () => {
  it("exposes only human-readable labels and values", () => {
    const chips = parsedChips(
      payload({ destinationCountries: ["JP"], tripPlan: "multi_city", directOnly: true }),
    );

    for (const c of chips) {
      expect(c.value).not.toMatch(/[{}[\]"]/);
      expect(c.value).not.toMatch(/_/);
      expect(c.label).not.toMatch(/[A-Z]{2,}/);
    }
  });
});

describe("dropping the budget ceiling", () => {
  it("stops offering a removal once the ceiling is already gone", () => {
    // Otherwise the chip invites an action that would change nothing.
    const chips = parsedChips(payload({ maxBudget: MAX_BUDGET_CEILING }));

    expect(chip(chips, "budget")!.removable).toBe(false);
    expect(chip(chips, "budget")!.value).toBe("No limit");
  });

  it("still offers it below the ceiling", () => {
    const chips = parsedChips(payload({ maxBudget: 900 }));

    expect(chip(chips, "budget")!.removable).toBe(true);
  });
});
