import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";

import { AuthProvider } from "../components/AuthContext";

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
  title: {
    default: "Triplet — Find cheap trips, not just cheap flights",
    template: "%s · Triplet",
  },
  description:
    "Choose your airports, set your travel style, and Triplet watches for unusually cheap fares that can become real trips.",
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
    <html lang="en">
      <body className={`${display.variable} ${sans.variable} ${mono.variable} font-sans`}>
        {/* Travelpayouts Drive: affiliate attribution/verification. beforeInteractive
            renders it into the server-side <head>, as Travelpayouts requires. */}
        <Script id="travelpayouts-drive" strategy="beforeInteractive">
          {`(function () {
              var script = document.createElement("script");
              script.async = 1;
              script.src = 'https://emrldtp.cc/NTQ3MDYz.js?t=547063';
              document.head.appendChild(script);
          })();`}
        </Script>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
