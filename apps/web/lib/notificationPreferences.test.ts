import { describe, expect, it } from "vitest";

import { watchDefaultsForPreference } from "./notificationPreferences";

describe("profile notification choices become real watch settings", () => {
  it("uses weekly checks for a weekly digest", () => {
    expect(watchDefaultsForPreference("weekly_digest", ["daily", "weekly"])).toEqual({
      frequency: "weekly",
      trigger: "any",
    });
  });

  it("uses route-deal filtering for urgent-only alerts", () => {
    expect(watchDefaultsForPreference("urgent_only", ["daily", "weekly"])).toEqual({
      frequency: "daily",
      trigger: "route_deal",
    });
  });

  it("does not create a daily watch when the plan only permits weekly checks", () => {
    expect(watchDefaultsForPreference("instant_email", ["weekly"])).toEqual({
      frequency: "weekly",
      trigger: "any",
    });
  });

  it("keeps the removed web-only push value safe for old profiles", () => {
    expect(watchDefaultsForPreference("push_later", ["daily", "weekly"]).frequency).toBe("weekly");
  });
});
