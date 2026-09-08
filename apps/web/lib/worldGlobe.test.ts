import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const globe = readFileSync(new URL("../components/TravelMapGlobe.tsx", import.meta.url), "utf8");

describe("My World country geometry", () => {
  it("rebuilds polygons when asynchronously loaded country features arrive", () => {
    expect(globe).toContain("[codeByNumeric, countryFeatures]");
  });
});
