import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("../app/verify-email/client.tsx", import.meta.url), "utf8");

describe("email verification page", () => {
  it("does not consume a one-time token merely because the link was opened", () => {
    const effect = source.slice(source.indexOf("useEffect(() =>"), source.indexOf("function verify("));

    expect(effect).toContain('setState({ status: "ready", token })');
    expect(effect).not.toContain('apiPost("/auth/verify-email"');
  });

  it("requires a deliberate confirmation action", () => {
    expect(source).toContain("Confirm my email");
    expect(source).toContain("onClick={() => verify(state.token)}");
  });

  it("explains an isolated mail browser and offers login", () => {
    expect(source).toContain("Your mail app opened this outside your Farelin session");
    expect(source).toContain('{user ? "Create travel profile" : "Log in"}');
  });

  it("supports the post-signup check-your-inbox state", () => {
    expect(source).toContain('status: "pending"');
    expect(source).toContain("Check your inbox.");
    expect(source).toContain("some email providers can take two or three minutes");
    expect(source).toContain('href={user ? "/onboarding" : "/login"}');
  });
});
