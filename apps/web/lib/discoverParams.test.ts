import { describe, expect, it } from "vitest";

import {
  discoverShareUrl,
  parseDiscoverSearchParams,
  serializeDiscoverSearchParams,
  type DiscoverSearchState,
} from "./discoverParams";

const defaults: DiscoverSearchState = {
  originAirports: [],
  destinationAirports: [],
  destinationCountries: [],
  destinationRegions: [],
  destinationContinents: [],
  excludeEurope: false,
  unvisitedOnly: false,
  returnOriginAirports: [],
  startDate: "2026-10-01",
  endDate: "2026-12-31",
  minTripLengthDays: 4,
  maxTripLengthDays: 8,
  maxBudget: 600,
  maxGroundTransferHours: 4,
  tripStyle: "surprise me",
  tripPlan: "return",
  directOnly: false,
};

const parse = (qs: string) => parseDiscoverSearchParams(new URLSearchParams(qs), defaults);

describe("sharing a structured search", () => {
  it("round-trips a whole search unchanged", () => {
    const search: DiscoverSearchState = {
      ...defaults,
      originAirports: ["VIE", "BUD"],
      destinationCountries: ["Japan"],
      startDate: "2026-10-01",
      endDate: "2026-10-31",
      minTripLengthDays: 8,
      maxTripLengthDays: 12,
      maxBudget: 900,
      tripPlan: "return",
      directOnly: true,
    };

    const params = serializeDiscoverSearchParams(search, defaults);
    expect(parseDiscoverSearchParams(params, defaults)).toEqual(search);
  });

  it("omits anything left at its default, so links stay short", () => {
    const params = serializeDiscoverSearchParams(
      { ...defaults, originAirports: ["VIE"] },
      defaults,
    );
    expect(params.toString()).toBe("from=VIE");
  });

  it("builds a link someone can paste", () => {
    const url = discoverShareUrl(
      { ...defaults, originAirports: ["VIE", "BUD"], maxBudget: 900 },
      defaults,
      { sort: "best" },
      "https://triplet.example",
    );
    expect(url).toBe("https://triplet.example/discover?from=VIE%2CBUD&budget=900&sort=best");
  });
});

describe("a URL is untrusted input", () => {
  it("drops codes that are not airports rather than searching for them", () => {
    expect(parse("from=VIE,not-a-code,BUD,12").originAirports).toEqual(["VIE", "BUD"]);
  });

  it("ignores a date that looks right but does not exist", () => {
    expect(parse("start=2026-02-31").startDate).toBe(defaults.startDate);
  });

  it("ignores nonsense in numeric fields", () => {
    expect(parse("budget=abc").maxBudget).toBe(defaults.maxBudget);
    expect(parse("budget=-5").maxBudget).toBe(defaults.maxBudget);
    expect(parse("minDays=0").minTripLengthDays).toBe(defaults.minTripLengthDays);
  });

  it("refuses a budget large enough to be a denial-of-service", () => {
    expect(parse("budget=99999999999").maxBudget).toBe(defaults.maxBudget);
  });

  it("caps how many airports a hand-edited link can request", () => {
    const many = Array.from({ length: 40 }, (_, i) => `A${String.fromCharCode(65 + (i % 26))}X`);
    expect(parse(`from=${many.join(",")}`).originAirports.length).toBeLessThanOrEqual(12);
  });

  it("rejects an enum it does not recognise", () => {
    expect(parse("plan=teleport").tripPlan).toBe(defaults.tripPlan);
    expect(parse("style=luxury").tripStyle).toBe(defaults.tripStyle);
  });

  it("repairs a reversed trip-length range instead of returning nothing", () => {
    const parsed = parse("minDays=10&maxDays=3");
    expect(parsed.minTripLengthDays).toBe(10);
    expect(parsed.maxTripLengthDays).toBe(10);
  });

  it("never throws, whatever arrives", () => {
    for (const qs of ["from=", "start=x&end=y&budget=&plan=", "%%%=%%%", "from=,,,,"]) {
      expect(() => parse(qs)).not.toThrow();
    }
  });
});

describe("what a shared link must never carry", () => {
  it("encodes no identity, contact or credential, whatever is in state", () => {
    const contaminated = {
      ...defaults,
      originAirports: ["VIE"],
      // Fields that do not belong in the schema, as a guard against someone
      // widening the state type later and quietly leaking one.
      email: "traveller@example.com",
      userId: "user_123",
      manageToken: "secret-token",
      plan: "pro",
    } as unknown as DiscoverSearchState;

    const encoded = serializeDiscoverSearchParams(contaminated, defaults).toString();

    for (const leak of ["traveller", "example.com", "user_123", "secret-token", "pro"]) {
      expect(encoded).not.toContain(leak);
    }
  });

  it("ignores identity parameters if someone adds them to a link by hand", () => {
    const parsed = parse("from=VIE&email=victim@example.com&userId=abc&token=xyz");
    expect(parsed.originAirports).toEqual(["VIE"]);
    expect(JSON.stringify(parsed)).not.toContain("victim@example.com");
    expect(JSON.stringify(parsed)).not.toContain("xyz");
  });
});
