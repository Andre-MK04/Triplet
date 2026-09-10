import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("../components/AuthContext.tsx", import.meta.url), "utf8");

describe("browser auth session persistence", () => {
  it("uses the persistent refresh cookie when the short access session expires", () => {
    expect(source).toContain('apiPost<AuthResponse>("/auth/refresh")');
  });

  it("synchronizes account changes between tabs without storing credentials", () => {
    expect(source).toContain('window.addEventListener("storage"');
    expect(source).toContain("AUTH_SYNC_KEY");
    expect(source).not.toContain("localStorage.setItem(ACCESS");
    expect(source).not.toContain("localStorage.setItem(REFRESH");
  });
});
