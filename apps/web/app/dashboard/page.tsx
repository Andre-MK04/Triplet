import type { Metadata } from "next";

import { DashboardClient } from "./client";

export const metadata: Metadata = { title: "Dashboard", robots: { index: false, follow: false } };

export default function DashboardPage() {
  return <DashboardClient />;
}
