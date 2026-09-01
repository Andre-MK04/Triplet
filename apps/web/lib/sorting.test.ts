import { describe, expect, it } from "vitest";

import { isSortKey, sortTrips, totalDurationMinutes, unsortableCount } from "./sorting";
import type { TripOption } from "./types";

/**
 * Result ordering.
 *
 * The case that matters most is missing data: a trip whose duration is unknown
 * must not be presented as the fastest one, and a fare with no observation time
 * must not be presented as the freshest.
 */

function flight(durationMinutes: number | null) {
  return {
    id: "f",
    origin: "VIE",
    destination: "BCN",
    departureDateTime: "2026-10-06T08:00:00",
    arrivalDateTime: "2026-10-06T10:00:00",
    price: 100,
    currency: "EUR",
    airline: "Test",
    durationMinutes,
  } as TripOption["outboundFlight"];
}

function trip(overrides: Partial<TripOption> & { id: string }): TripOption {
  return {
    tripType: "same_city",
    outboundFlight: flight(120),
    returnFlight: flight(120),
    totalPrice: 200,
    score: 50,
    nights: 5,
    tripLengthDays: 6,
    tags: [],
    warnings: [],
    explanation: "",
    ...overrides,
  } as TripOption;
}

describe("sort keys", () => {
  it("accepts the four real orderings and nothing else", () => {
    expect(isSortKey("best")).toBe(true);
    expect(isSortKey("cheapest")).toBe(true);
    expect(isSortKey("freshest")).toBe(true);
    expect(isSortKey("fastest")).toBe(true);
    expect(isSortKey("price-desc")).toBe(false);
    expect(isSortKey(null)).toBe(false);
  });
});

describe("best", () => {
  it("puts the highest Triplet score first", () => {
    const trips = [
      trip({ id: "low", dealScore: 40 }),
      trip({ id: "high", dealScore: 90 }),
      trip({ id: "mid", dealScore: 65 }),
    ];

    expect(sortTrips(trips, "best").map((t) => t.id)).toEqual(["high", "mid", "low"]);
  });

  it("breaks a tie on price so the order is stable and sensible", () => {
    const trips = [
      trip({ id: "dear", dealScore: 80, totalPrice: 400 }),
      trip({ id: "cheap", dealScore: 80, totalPrice: 100 }),
    ];

    expect(sortTrips(trips, "best").map((t) => t.id)).toEqual(["cheap", "dear"]);
  });

  it("does not mutate the array it was given", () => {
    const trips = [trip({ id: "a", dealScore: 10 }), trip({ id: "b", dealScore: 90 })];

    sortTrips(trips, "best");

    expect(trips.map((t) => t.id)).toEqual(["a", "b"]);
  });
});

describe("cheapest", () => {
  it("orders by trip total, lowest first", () => {
    const trips = [
      trip({ id: "c", totalPrice: 300 }),
      trip({ id: "a", totalPrice: 100 }),
      trip({ id: "b", totalPrice: 200 }),
    ];

    expect(sortTrips(trips, "cheapest").map((t) => t.id)).toEqual(["a", "b", "c"]);
  });

  it("ignores the Triplet score entirely", () => {
    const trips = [
      trip({ id: "great-but-dear", dealScore: 99, totalPrice: 500 }),
      trip({ id: "poor-but-cheap", dealScore: 10, totalPrice: 50 }),
    ];

    expect(sortTrips(trips, "cheapest")[0].id).toBe("poor-but-cheap");
  });
});

describe("freshest", () => {
  it("orders by how recently the fare was observed", () => {
    const trips = [
      trip({ id: "old", price: { ageHours: 40 } as TripOption["price"] }),
      trip({ id: "new", price: { ageHours: 2 } as TripOption["price"] }),
      trip({ id: "mid", price: { ageHours: 12 } as TripOption["price"] }),
    ];

    expect(sortTrips(trips, "freshest").map((t) => t.id)).toEqual(["new", "mid", "old"]);
  });

  it("puts fares with no observation time last, not first", () => {
    const trips = [
      trip({ id: "unknown" }),
      trip({ id: "known", price: { ageHours: 30 } as TripOption["price"] }),
    ];

    expect(sortTrips(trips, "freshest").map((t) => t.id)).toEqual(["known", "unknown"]);
  });
});

describe("fastest", () => {
  it("orders by total flying time", () => {
    const trips = [
      trip({ id: "slow", outboundFlight: flight(400), returnFlight: flight(400) }),
      trip({ id: "quick", outboundFlight: flight(90), returnFlight: flight(90) }),
    ];

    expect(sortTrips(trips, "fastest").map((t) => t.id)).toEqual(["quick", "slow"]);
  });

  it("treats a trip with any unknown leg as unknown rather than fast", () => {
    // Summing only the legs that report a duration would rank this trip on the
    // strength of the one leg we know about.
    const trips = [
      trip({ id: "partial", outboundFlight: flight(60), returnFlight: flight(null) }),
      trip({ id: "known", outboundFlight: flight(300), returnFlight: flight(300) }),
    ];

    expect(sortTrips(trips, "fastest").map((t) => t.id)).toEqual(["known", "partial"]);
  });

  it("keeps trips with no duration at the end and counts them", () => {
    const trips = [
      trip({ id: "none", outboundFlight: flight(null), returnFlight: flight(null) }),
      trip({ id: "timed", outboundFlight: flight(100), returnFlight: flight(100) }),
    ];

    expect(sortTrips(trips, "fastest").map((t) => t.id)).toEqual(["timed", "none"]);
    expect(unsortableCount(trips, "fastest")).toBe(1);
  });

  it("reports no total duration when a leg is missing one", () => {
    expect(totalDurationMinutes(trip({ id: "x", returnFlight: flight(null) }))).toBeNull();
    expect(totalDurationMinutes(trip({ id: "y" }))).toBe(240);
  });
});
