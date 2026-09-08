import type { Metadata } from "next";

import { ContactClient } from "./client";

export const metadata: Metadata = {
  title: "Contact us",
  description: "Contact Farelin about your account, a fare, privacy, security, or a partnership.",
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return <ContactClient />;
}
