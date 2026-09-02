import { describe, expect, it } from "vitest";

import { tripPreviewDescription, tripPreviewTitle, tripRouteLabel } from "./tripPreview";
import type { TripOption } from "./types";

const flight = (origin: string, destination: string, depart: string, arrive: string) =>
  ({
    id: `${origin}-${destination}`,
    origin,
    destination,
    departureDateTime: depart,
    arrivalDateTime: arrive,
    airline: "OS",
    price: 210,
    currency: "EUR",
  }) as TripOption["outboundFlight"];

const base = {
  id: "t1",
  tripType: "same_city",
  outboundFlight: flight("VIE", "TYO", "2026-10-12T09:00:00", "2026-10-12T20:00:00"),
  returnFlight: flight("TYO", "VIE", "2026-10-19T10:00:00", "2026-10-19T18:00:00"),
  groundTransfer: null,
  totalPrice: 421,
  tripLengthDays: 8,
  nights: 7,
  score: 90,
} as unknown as TripOption;

describe("what a shared trip link says when it unfurls", () => {
  it("names the route, the length and the fare", () => {
    const title = tripPreviewTitle(base);
    expect(title).toContain("→");
    expect(title).toContain("7 nights");
    expect(title).toContain("€421");
  });

  it("describes a fare as observed, never as bookable", () => {
    const description = tripPreviewDescription(base);
    expect(description).toContain("observed fare from €421");
    expect(description).toContain("check the live price before booking");
    expect(description).not.toMatch(/book (for|at) €/i);
    expect(description).not.toMatch(/live €/i);
    expect(description).not.toContain("guaranteed");
  });

  it("carries the dates", () => {
    expect(tripPreviewDescription(base)).toMatch(/12 Oct/);
  });

  it("reads an open jaw as two different legs", () => {
    const openJaw = {
      ...base,
      tripType: "open_jaw",
      outboundFlight: flight("VIE", "ARN", "2026-10-12T09:00:00", "2026-10-12T11:00:00"),
      returnFlight: flight("HEL", "VIE", "2026-10-19T10:00:00", "2026-10-19T12:00:00"),
    } as unknown as TripOption;

    const label = tripRouteLabel(openJaw);
    expect(label).toContain("·");
    // The home leg starts somewhere the outbound never reached — that is the
    // whole point of an open jaw and the preview must not hide it.
    expect(label.split("·")[0]).not.toEqual(label.split("·")[1]);
  });

  it("reads a multi-city trip as the chain it is, not first-and-last", () => {
    const multi = {
      ...base,
      tripType: "multi_city",
      segments: [
        { kind: "flight", origin: "VIE", destination: "ROM", originCity: "Vienna", destinationCity: "Rome", departureDate: "2026-10-12" },
        { kind: "flight", origin: "ROM", destination: "ATH", originCity: "Rome", destinationCity: "Athens", departureDate: "2026-10-15" },
        { kind: "flight", origin: "ATH", destination: "IST", originCity: "Athens", destinationCity: "Istanbul", departureDate: "2026-10-18" },
      ],
    } as unknown as TripOption;

    const label = tripRouteLabel(multi);
    expect(label).toBe("Vienna → Rome → Athens → Istanbul");
  });

  it("keeps titles short enough for a social preview", () => {
    const longChain = {
      ...base,
      tripType: "multi_city",
      segments: Array.from({ length: 9 }, (_, i) => ({
        kind: "flight",
        origin: "AAA",
        destination: "BBB",
        originCity: `Cityname${i}`,
        destinationCity: `Cityname${i + 1}`,
        departureDate: "2026-10-12",
      })),
    } as unknown as TripOption;

    expect(tripPreviewTitle(longChain).length).toBeLessThanOrEqual(70);
  });

  it("degrades rather than throwing when a trip is missing pieces", () => {
    const sparse = { tripType: "same_city", outboundFlight: flight("VIE", "TYO", "", "") } as unknown as TripOption;
    expect(() => tripPreviewTitle(sparse)).not.toThrow();
    expect(() => tripPreviewDescription(sparse)).not.toThrow();
  });
});

describe("dates that contradict themselves", () => {
  it("prints one date rather than a range that argues with the night count", () => {
    // Real cached trips have shown a return leg dated the same day as the
    // outbound while still reporting several nights. "7 Nov – 7 Nov · 4 nights"
    // is a visible contradiction in whatever chat app the link lands in.
    const inconsistent = {
      ...base,
      nights: 4,
      outboundFlight: flight("VIE", "VCE", "2026-11-07T09:00:00", "2026-11-07T10:19:00"),
      returnFlight: flight("VCE", "VIE", "2026-11-07T18:00:00", "2026-11-07T19:19:00"),
    } as unknown as TripOption;

    const description = tripPreviewDescription(inconsistent);
    expect(description).toContain("7 Nov");
    expect(description).not.toContain("7 Nov – 7 Nov");
  });

  it("still prints a range when the dates make sense", () => {
    expect(tripPreviewDescription(base)).toMatch(/12 Oct – 19 Oct/);
  });
});
