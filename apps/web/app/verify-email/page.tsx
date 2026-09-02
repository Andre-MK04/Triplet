import type { Metadata } from "next";
import { Suspense } from "react";

import { VerifyEmailClient } from "./client";

export const metadata: Metadata = {
  title: "Confirm your email",
  // Single-use, personal to one inbox, and useless to anyone else. Nothing
  // here is worth indexing and every reason not to.
  robots: { index: false, follow: false },
};

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailClient />
    </Suspense>
  );
}
