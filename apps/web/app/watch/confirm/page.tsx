import type { Metadata } from "next";
import { Suspense } from "react";

import { WatchConfirmClient } from "./client";

export const metadata: Metadata = {
  title: "Confirm your watch",
  // A confirmation link is single-use and personal to one inbox; there is
  // nothing here worth indexing and every reason not to.
  robots: { index: false, follow: false },
};

export default function WatchConfirmPage() {
  return (
    <Suspense>
      <WatchConfirmClient />
    </Suspense>
  );
}
