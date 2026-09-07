import type { TravelProfile } from "./types";
import type { WatchTriggerMode } from "./watchTriggers";

export type WatchNotificationDefaults = {
  frequency: "daily" | "weekly";
  trigger: WatchTriggerMode;
};

/**
 * Turn the profile's human notification choice into fields the watch runner
 * actually enforces. The plan's allowed frequencies remain authoritative: a
 * Free account asking for prompt alerts receives weekly checks rather than a
 * watch the backend would reject.
 */
export function watchDefaultsForPreference(
  preference: TravelProfile["notificationFrequency"],
  allowedFrequencies: string[],
): WatchNotificationDefaults {
  const fastest = allowedFrequencies.includes("daily") ? "daily" : "weekly";

  if (preference === "weekly_digest" || preference === "push_later") {
    return { frequency: "weekly", trigger: "any" };
  }
  if (preference === "urgent_only") {
    return { frequency: fastest, trigger: "route_deal" };
  }
  return { frequency: fastest, trigger: "any" };
}
