import { readFileSync } from "node:fs";

import { afterEach, describe, expect, it } from "vitest";

import { BRAND } from "./brand";
import { siteUrl } from "./site";

const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const shell = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");
const authForm = readFileSync(new URL("../components/AuthForm.tsx", import.meta.url), "utf8");
const nextConfig = readFileSync(new URL("../next.config.ts", import.meta.url), "utf8");
const pricing = readFileSync(new URL("../app/pricing/page.tsx", import.meta.url), "utf8");
const discover = readFileSync(new URL("../app/discover/page.tsx", import.meta.url), "utf8");
const privacy = readFileSync(new URL("../app/privacy/client.tsx", import.meta.url), "utf8");
const terms = readFileSync(new URL("../app/terms/client.tsx", import.meta.url), "utf8");
const security = readFileSync(new URL("../app/security/client.tsx", import.meta.url), "utf8");
const sitemap = readFileSync(new URL("../app/sitemap.ts", import.meta.url), "utf8");
const robots = readFileSync(new URL("../app/robots.ts", import.meta.url), "utf8");

describe("Farelin public identity", () => {
  const originalSiteUrl = process.env.NEXT_PUBLIC_SITE_URL;

  afterEach(() => {
    if (originalSiteUrl === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
    else process.env.NEXT_PUBLIC_SITE_URL = originalSiteUrl;
  });

  it("centralizes the public name and tagline", () => {
    expect(BRAND.name).toBe("Farelin");
    expect(BRAND.domain).toBe(new URL(BRAND.url).hostname);
    expect(BRAND.tagline).toBe("Find cheap trips, not just cheap flights");
    expect(layout).toContain("BRAND.name");
    expect(shell).toContain("BRAND.name");
    expect(authForm).toContain("BRAND.name");
    expect(layout).toContain("applicationName: BRAND.name");
    expect(layout).toContain("siteName: BRAND.name");
  });

  it("uses Farelin on current public product and legal surfaces", () => {
    expect(pricing).toContain("Farelin");
    expect(discover).toContain("Farelin");
    expect(privacy).toContain("Farelin");
    expect(terms).toContain("Farelin");
    expect(security).toContain("Farelin");
  });

  it("uses the configured Farelin origin for canonicals, sitemap and robots", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://farelin.com/";
    expect(siteUrl()).toBe("https://farelin.com");
    expect(sitemap).toContain("siteUrl()");
    expect(robots).toContain("siteUrl()");
  });

  it("redirects only the exact old production host", () => {
    expect(nextConfig).toContain('value: "triplet-web.vercel.app"');
    expect(nextConfig).not.toContain('value: "www.farelin.com"');
    expect(nextConfig).not.toContain('value: "*.vercel.app"');
  });
});
