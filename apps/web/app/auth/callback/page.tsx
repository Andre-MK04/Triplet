import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCallbackClient } from "./client";

export const metadata: Metadata = { title: "Signing you in" };

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <AuthCallbackClient />
    </Suspense>
  );
}
