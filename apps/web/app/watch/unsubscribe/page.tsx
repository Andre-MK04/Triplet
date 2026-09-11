import type { Metadata } from "next";

import { WatchUnsubscribeClient } from "./client";

export const metadata: Metadata = {
  title: "Unsubscribe from a watch",
  robots: { index: false, follow: false },
};

export default function WatchUnsubscribePage() {
  return <WatchUnsubscribeClient />;
}
