import { beforeEach, describe, expect, it } from "vitest";

import {
  ASK_AFTER_MS,
  ASK_BEFORE_MS,
  MIN_MS_BETWEEN_ASKS,
  fareCheckToAsk,
  forgetAllFareChecks,
  rememberFareCheck,
  settleFareCheck,
} from "./fareCheck";
import type { TripOption } from "./types";

/**
 * When Triplet may ask how a fare held up.
 *
 * The research signal is worth little and the cost of getting this wrong is
 * high: a product that interviews people every visit is a product they stop
 * visiting. These tests are mostly about when the question must NOT appear.
 */

function trip(overrides: Partial<TripOption> = {}): TripOption {
  return {
    id: "t1",
    tripType: "same_city",
    outboundFlight: { origin: "VIE", destination: "BCN" },
    returnFlight: { origin: "BCN", destination: "VIE" },
    totalPrice: 120,
    destination: { city: "Barcelona" },
    provider: "travelpayouts",
    price: { kind: "cached_return", currency: "EUR", freshness: "fresh" },
    ...overrides,
  } as unknown as TripOption;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("remembering a check", () => {
  it("records nothing until a fare is actually checked", () => {
    expect(fareCheckToAsk()).toBeNull();
  });

  it("keeps the fare's properties and not the traveller's", () => {
    rememberFareCheck(trip());

    const stored = JSON.parse(window.localStorage.getItem("triplet.fareChecks.v1")!);
    const keys = Object.keys(stored[0]);
    expect(keys).not.toContain("email");
    expect(keys).not.toContain("userId");
    expect(stored[0].origin).toBe("VIE");
    expect(stored[0].fareAgeBucket).toBe("fresh");
  });

  it("ignores a trip with no price model to describe", () => {
    rememberFareCheck(trip({ price: null }));

    expect(fareCheckToAsk()).toBeNull();
  });

  it("gives every check its own id", () => {
    rememberFareCheck(trip());
    rememberFareCheck(trip());

    const stored = JSON.parse(window.localStorage.getItem("triplet.fareChecks.v1")!);
    expect(new Set(stored.map((c: { checkId: string }) => c.checkId)).size).toBe(2);
  });
});

describe("when the question may appear", () => {
  it("stays quiet immediately after the click", () => {
    // They are still on the provider's site; there is nothing to report yet.
    rememberFareCheck(trip());

    expect(fareCheckToAsk()).toBeNull();
  });

  it("asks once enough time has passed", () => {
    rememberFareCheck(trip());

    expect(fareCheckToAsk(Date.now() + ASK_AFTER_MS + 1000)).not.toBeNull();
  });

  it("stops asking once the memory would be unreliable", () => {
    rememberFareCheck(trip());

    expect(fareCheckToAsk(Date.now() + ASK_BEFORE_MS + 1000)).toBeNull();
  });

  it("asks about the most recent check, which is best remembered", () => {
    rememberFareCheck(trip({ destination: { city: "Barcelona" } } as Partial<TripOption>));
    rememberFareCheck(trip({ outboundFlight: { origin: "VIE", destination: "PMO" } } as Partial<TripOption>));

    const asked = fareCheckToAsk(Date.now() + ASK_AFTER_MS + 1000);

    expect(asked!.destination).toBe("PMO");
  });
});

describe("never nagging", () => {
  it("never raises the same check twice", () => {
    rememberFareCheck(trip());
    const later = Date.now() + ASK_AFTER_MS + 1000;
    const asked = fareCheckToAsk(later)!;

    settleFareCheck(asked.checkId, later);

    expect(fareCheckToAsk(later + 1000)).toBeNull();
  });

  it("asks at most once a day however many fares are checked", () => {
    rememberFareCheck(trip());
    const first = Date.now() + ASK_AFTER_MS + 1000;
    settleFareCheck(fareCheckToAsk(first)!.checkId, first);

    // A second check, ripe, but too soon after the last question.
    rememberFareCheck(trip());
    expect(fareCheckToAsk(first + ASK_AFTER_MS + 2000)).toBeNull();

    // A day later it may ask again.
    expect(fareCheckToAsk(first + MIN_MS_BETWEEN_ASKS + 1000)).not.toBeNull();
  });

  it("honours being told to stop", () => {
    rememberFareCheck(trip());
    const later = Date.now() + ASK_AFTER_MS + 1000;

    forgetAllFareChecks();

    expect(fareCheckToAsk(later)).toBeNull();
    expect(fareCheckToAsk(later + MIN_MS_BETWEEN_ASKS + 1000)).toBeNull();
  });

  it("does not grow without bound as fares are checked", () => {
    for (let i = 0; i < 30; i += 1) rememberFareCheck(trip());

    const stored = JSON.parse(window.localStorage.getItem("triplet.fareChecks.v1")!);
    expect(stored.length).toBeLessThanOrEqual(8);
  });
});

describe("storage failures are survivable", () => {
  it("asks nothing rather than throwing when storage is unavailable", () => {
    const original = window.localStorage;
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("storage disabled");
      },
      configurable: true,
    });

    expect(() => fareCheckToAsk()).not.toThrow();
    expect(fareCheckToAsk()).toBeNull();

    Object.defineProperty(window, "localStorage", { value: original, configurable: true });
  });
});
