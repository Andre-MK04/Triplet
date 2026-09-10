import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("../components/AuthForm.tsx", import.meta.url), "utf8");

describe("password signup verification flow", () => {
  it("routes an unverified password signup to the inbox step", () => {
    expect(source).toContain("const newUser = await signup");
    expect(source).toContain('newUser.isVerified ? "/onboarding" : "/verify-email?sent=1"');
  });

  it("keeps Google OAuth on its separate provider flow", () => {
    expect(source).toContain("/auth/oauth/google/start");
  });
});
