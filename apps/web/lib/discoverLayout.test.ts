import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const discover = readFileSync(new URL("../app/discover/client.tsx", import.meta.url), "utf8");
const home = readFileSync(new URL("../app/home-client.tsx", import.meta.url), "utf8");
const world = readFileSync(new URL("../app/world/client.tsx", import.meta.url), "utf8");

describe("Discover search access", () => {
  it("restores the always-visible AI prompt and trip-shape controls", () => {
    expect(discover).toContain('id="ai-trip-input"');
    expect(discover).not.toContain("askOpen");
    expect(discover.indexOf("<TripPlanChoice")).toBeGreaterThan(-1);
    expect(discover.indexOf("<TripPlanChoice")).toBeLessThan(discover.indexOf("aria-expanded={refineOpen}"));
    expect(discover).toContain('"Dates, budget, destination +"');
  });

  it("restores the homepage search box and original hero", () => {
    expect(home).toContain("<HeroSearch />");
    expect(home).toContain("Europe,");
    expect(home).toContain("on a whim.");
    expect(home).not.toContain("QuickStart");
  });

  it("removes app-style opportunity boards from the restored web pages", () => {
    for (const source of [discover, home, world]) {
      expect(source).not.toContain("OpportunityRail");
      expect(source).not.toContain("useOpportunities");
      expect(source).not.toContain("QuickSearchControls");
    }
  });
});
