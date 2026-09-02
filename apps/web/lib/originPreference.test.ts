import { beforeEach, describe, expect, it, vi } from "vitest";

import { forgetSavedOrigins, readSavedOrigins, saveOrigins } from "./originPreference";

describe("remembering where an anonymous traveller flies from", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("has no opinion until asked — the old Vienna default is not a fallback", () => {
    expect(readSavedOrigins()).toEqual([]);
  });

  it("returns what was chosen, on the next visit", () => {
    saveOrigins(["LIS", "OPO"]);
    expect(readSavedOrigins()).toEqual(["LIS", "OPO"]);
  });

  it("forgets the list when every airport is deselected", () => {
    saveOrigins(["LIS"]);
    saveOrigins([]);
    // Keeping the old list here would resurrect a choice the traveller undid.
    expect(readSavedOrigins()).toEqual([]);
    expect(window.localStorage.getItem("triplet.origins.v1")).toBeNull();
  });

  it("normalises case and drops duplicates", () => {
    saveOrigins(["lis", "LIS", "opo"]);
    expect(readSavedOrigins()).toEqual(["LIS", "OPO"]);
  });

  it("ignores anything that is not an airport code", () => {
    window.localStorage.setItem(
      "triplet.origins.v1",
      JSON.stringify(["LIS", "not-a-code", 42, null, "PORTUGAL"]),
    );
    expect(readSavedOrigins()).toEqual(["LIS"]);
  });

  it("survives storage holding something that is not a list", () => {
    window.localStorage.setItem("triplet.origins.v1", '{"origins":"LIS"}');
    expect(readSavedOrigins()).toEqual([]);
  });

  it("survives storage holding malformed JSON", () => {
    window.localStorage.setItem("triplet.origins.v1", "{not json");
    expect(readSavedOrigins()).toEqual([]);
  });

  it("does not fail a search when the browser refuses to store", () => {
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("QuotaExceededError");
      });

    expect(() => saveOrigins(["LIS"])).not.toThrow();
    setItem.mockRestore();
  });

  it("does not fail a read when the browser refuses to be read", () => {
    const getItem = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new Error("SecurityError");
      });

    expect(readSavedOrigins()).toEqual([]);
    getItem.mockRestore();
  });

  it("caps a runaway list rather than storing it whole", () => {
    // Real three-letter codes, or the regex would reject them all and the cap
    // would appear to work while never being reached.
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const many = Array.from({ length: 40 }, (_, i) => `X${letters[i % 26]}${letters[(i * 7) % 26]}`);
    const distinct = new Set(many);
    expect(distinct.size).toBeGreaterThan(12);

    saveOrigins([...distinct]);

    expect(readSavedOrigins().length).toBe(12);
  });

  it("clears on request", () => {
    saveOrigins(["LIS"]);
    forgetSavedOrigins();
    expect(readSavedOrigins()).toEqual([]);
  });
});
