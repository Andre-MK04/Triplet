import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "../components/AuthContext";
import { BRAND } from "../lib/brand";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["400", "500", "700", "800"],
  variable: "--font-display",
});
const sans = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  // Absolute URLs for Open Graph and canonicals are resolved against this.
  metadataBase: new URL(BRAND.url),
  applicationName: BRAND.name,
  title: {
    default: `${BRAND.name} — ${BRAND.tagline}`,
    template: `%s · ${BRAND.name}`,
  },
  description:
    `Choose your airports and travel style, and ${BRAND.name} finds unusually good observed fares that can become real trips.`,
  // Deliberately no canonical here. Next merges parent metadata into children,
  // so a canonical on the root layout is inherited by every page that does not
  // set its own — telling crawlers that /pricing, /terms and /security are all
  // really the homepage. Each stable public page declares its own instead.
  openGraph: {
    type: "website",
    siteName: BRAND.name,
    title: `${BRAND.name} — ${BRAND.tagline}`,
    description:
      "Flexible trip discovery from the airports you choose, with every fare shown as what it is: recently observed, never guaranteed.",
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: `${BRAND.name} — ${BRAND.tagline}`,
    description:
      "Flexible trip discovery from the airports you choose, with every fare shown as what it is: recently observed, never guaranteed.",
  },
  // Keep the filename content-versioned. Safari maintains its own persistent
  // site-icon cache and can ignore changed bytes at a familiar /icon.png URL.
  // Explicit declarations also cover pinned/shortcut and Apple surfaces.
  icons: {
    icon: [
      {
        url: "/farelin-app-icon-7f83cc1f.png",
        type: "image/png",
        sizes: "1000x1000",
      },
    ],
    shortcut: ["/farelin-app-icon-7f83cc1f.png"],
    apple: [
      {
        url: "/farelin-app-icon-7f83cc1f.png",
        type: "image/png",
        sizes: "1000x1000",
      },
    ],
  },
};

export const viewport: Viewport = {
  themeColor: "#0b1117",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${display.variable} ${sans.variable} ${mono.variable} font-sans`}>
        {/* Same-origin external script: runs before paint without weakening script-src. */}
        <script src="/theme-init.js" />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
