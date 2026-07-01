import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Triplet",
  description: "Triplet helps you find cheap European trips with smart open-jaw routes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
