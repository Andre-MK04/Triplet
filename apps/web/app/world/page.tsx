import { TravelMapClient } from "./client";

export const metadata = {
  title: "My World",
  description: "Keep track of the countries you have visited, lived in, and want to explore next.",
  robots: { index: false, follow: false },
};

export default function WorldPage() {
  return <TravelMapClient />;
}
