import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiGet } from "./api";

/**
 * What a caller sees when the request never reaches the server.
 *
 * Every page renders `error.message` straight into a Notice, and that Notice is
 * announced assertively to screen readers — so a raw "Failed to fetch" is both
 * meaningless copy and something a person hears read aloud.
 */
describe("network failures", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("replaces the browser's fetch rejection with wording a traveller can act on", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    await expect(apiGet("/deals")).rejects.toSatisfy((error: unknown) => {
      expect(error).toBeInstanceOf(ApiError);
      const api = error as ApiError;
      expect(api.message).not.toMatch(/failed to fetch/i);
      expect(api.message).toContain("couldn't reach Triplet");
      // Status 0 marks "no response at all", so callers can distinguish a
      // connection problem from a server that answered with an error.
      expect(api.status).toBe(0);
      return true;
    });
  });

  it("still reports a real HTTP error from the server, not the offline message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        statusText: "Too Many Requests",
        json: async () => ({ detail: "Slow down." }),
      } as unknown as Response),
    );

    await expect(apiGet("/deals")).rejects.toMatchObject({
      status: 429,
      message: "Slow down.",
    });
  });
});
