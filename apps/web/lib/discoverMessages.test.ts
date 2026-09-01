import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { emptyStateMessage, limitAwareError, providerNotice } from "./discoverMessages";
import type { ProviderMetadata, TripSearchPayload } from "./types";

/**
 * What Discover tells a traveller when a search does not simply work.
 *
 * These three decide what someone believes about a result: whether the prices
 * are live, whether an empty page means Triplet did not look, and whether an
 * error is theirs or ours. They were unreachable inside a thousand-line client
 * component.
 */

function metadata(overrides: Partial<ProviderMetadata> = {}): ProviderMetadata {
  return {
    providerUsed: "hybrid",
    liveProviderAttempted: false,
    liveProviderSucceeded: false,
    cachedResultsUsed: false,
    providerWarnings: [],
    ...overrides,
  } as ProviderMetadata;
}

function payload(overrides: Partial<TripSearchPayload> = {}): TripSearchPayload {
  return { destinationAirports: null, destinationCountries: [], destinationRegions: [],
    destinationContinents: [], excludeEurope: false, ...overrides } as TripSearchPayload;
}

describe("saying where prices came from", () => {
  it("says nothing when there is nothing to caveat", () => {
    expect(providerNotice(null)).toBeNull();
    expect(providerNotice(metadata({ liveProviderSucceeded: true }))).toBeNull();
  });

  it("warns when a live source was tried and failed", () => {
    // The traveller must not read cached fares as live ones.
    const notice = providerNotice(metadata({ liveProviderAttempted: true, liveProviderSucceeded: false }));

    expect(notice!.tone).toBe("warning");
    expect(notice!.text).toMatch(/cached|out of date/i);
  });

  it("prefers the provider's own explanation when it gave one", () => {
    const notice = providerNotice(
      metadata({
        liveProviderAttempted: true,
        liveProviderSucceeded: false,
        providerWarnings: ["Travelpayouts rate limit reached."],
      }),
    );

    expect(notice!.text).toBe("Travelpayouts rate limit reached.");
  });

  it("always labels development data as illustrative", () => {
    const notice = providerNotice(metadata({ cachedResultsUsed: true }));

    expect(notice!.text).toMatch(/illustrative, not live/i);
  });

  it("passes a warning through when results did come back", () => {
    const notice = providerNotice(
      metadata({ liveProviderSucceeded: true, providerWarnings: ["Some routes were skipped."] }),
      5,
    );

    expect(notice).toEqual({ tone: "info", text: "Some routes were skipped." });
  });

  it("stays quiet about a warning when nothing came back anyway", () => {
    // The empty state explains itself; a second message competes with it.
    expect(
      providerNotice(metadata({ liveProviderSucceeded: true, providerWarnings: ["x"] }), 0),
    ).toBeNull();
  });
});

describe("explaining an empty result", () => {
  it("says Triplet did look, when a destination was named", () => {
    // Suggesting more origin airports here would imply a limit of Triplet's
    // rather than a thinness of the fares, and send them to fix the wrong thing.
    const message = emptyStateMessage(payload({ destinationAirports: ["NRT"] }));

    expect(message).toMatch(/checked that destination directly/i);
    expect(message).not.toMatch(/adding more origin airports/i);
  });

  it("names countries when the scope was a country or region", () => {
    expect(emptyStateMessage(payload({ destinationCountries: ["JP"] }))).toMatch(/those countries/i);
    expect(emptyStateMessage(payload({ destinationRegions: ["scandinavia"] }))).toMatch(/those countries/i);
  });

  it("explains that long-haul is thin when Europe was excluded", () => {
    expect(emptyStateMessage(payload({ excludeEurope: true }))).toMatch(/long-haul/i);
  });

  it("suggests what to widen when no destination was named", () => {
    expect(emptyStateMessage(payload())).toMatch(/budget|origin airports|ground transfers/i);
  });

  it("copes with no search at all", () => {
    expect(emptyStateMessage(null)).toBeTruthy();
  });
});

describe("turning an error into something actionable", () => {
  it("passes a quota message through, since it already names the plan", () => {
    const error = new ApiError(402, "You've used all 5 AI searches on the free plan.");

    expect(limitAwareError(error)).toBe("You've used all 5 AI searches on the free plan.");
  });

  it("explains a rate limit as a pause rather than a failure", () => {
    expect(limitAwareError(new ApiError(429, "Too many requests."))).toMatch(/few seconds/i);
  });

  it("uses the API's message for anything else", () => {
    expect(limitAwareError(new ApiError(500, "Database is not ready."))).toBe("Database is not ready.");
  });

  it("never surfaces a raw non-error value", () => {
    expect(limitAwareError("something odd")).toBe("Something went wrong.");
    expect(limitAwareError(null)).toBe("Something went wrong.");
  });
});
