import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "./globals.css";

import { AuthProvider } from "../components/AuthContext";

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
      <body className="font-sans">
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
