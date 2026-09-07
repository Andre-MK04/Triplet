import { describe, expect, it } from "vitest";

import { globeControlsEnabled } from "./globeMotion";

describe("globe controller", () => {
  it("keeps a non-interactive auth globe rotating", () => {
    expect(globeControlsEnabled(false, true)).toBe(true);
  });

  it("fully stops decorative motion when reduced motion applies", () => {
    expect(globeControlsEnabled(false, false)).toBe(false);
  });
});
