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
    expect(source).toContain('{user ? "Find trips" : "Log in"}');
  });
});
