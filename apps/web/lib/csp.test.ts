import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

/**
 * Triplet loads no third-party scripts.
 *
 * Affiliate commission rides on the `marker` query parameter the API writes
 * into each Aviasales booking URL, so the Travelpayouts Drive script was never
 * what earned it — it was behavioural JS on every page with the ability to
 * rewrite outbound links. These read the config source directly, because the
 * policy is assembled at module load from NODE_ENV and importing it under test
 * would only ever exercise one branch.
 */

const source = readFileSync(new URL("../next.config.ts", import.meta.url), "utf8");

describe("content security policy", () => {
  it("names no Travelpayouts Drive origin", () => {
    expect(source).not.toContain("emrldtp");
  });

  it("allows no third-party script host", () => {
    const scriptSrc = source.match(/`script-src[^`]*`/)?.[0] ?? "";

    expect(scriptSrc).toBeTruthy();
    expect(scriptSrc).not.toMatch(/https?:\/\/[a-z]/i);
    expect(scriptSrc).toContain("'self'");
  });

  it("grants unsafe-eval only outside production", () => {
    // Next.js needs it for dev tooling and React Refresh; a production build
    // does not, and granting it there would weaken the policy for nothing.
    expect(source).toMatch(/isDev \? " 'unsafe-eval'" : ""/);
  });

  it("still restricts connect-src to self and the API", () => {
    const connectSrc = source.match(/`connect-src[^`]*`/)?.[0] ?? "";

    expect(connectSrc).toContain("'self'");
    expect(connectSrc).not.toContain("*");
  });

  it("keeps the framing and object protections", () => {
    expect(source).toContain("frame-ancestors 'none'");
    expect(source).toContain("object-src 'none'");
    expect(source).toContain("base-uri 'self'");
  });
});
