import type { Metadata } from "next";

import { HomeClient } from "./home-client";

export const metadata: Metadata = {
  // Declared here rather than inherited. The root layout deliberately sets no
  // canonical, because Next merges parent metadata into children and a
  // canonical on the layout would tell crawlers every page is really "/".
  alternates: { canonical: "/" },
};

export default function HomePage() {
  return <HomeClient />;
}
