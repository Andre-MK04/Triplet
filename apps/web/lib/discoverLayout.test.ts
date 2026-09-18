import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const discover = readFileSync(new URL("../app/discover/client.tsx", import.meta.url), "utf8");
const rail = readFileSync(new URL("../components/OpportunityRail.tsx", import.meta.url), "utf8");

describe("Discover search access", () => {
  it("places the search composer before the signed-in opportunity feed", () => {
    const composer = discover.indexOf("<form onSubmit={runSearch}");
    const feed = discover.indexOf("<OpportunityRail");
    expect(composer).toBeGreaterThan(-1);
    expect(feed).toBeGreaterThan(-1);
    expect(composer).toBeLessThan(feed);
  });

  it("gives fare-board search links a real composer target", () => {
    expect(discover).toContain('id="trip-search"');
    expect(rail).toContain('href="/discover#trip-search"');
  });
});
