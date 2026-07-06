import type { NextConfig } from "next";
import path from "node:path";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

// 'unsafe-inline'/'unsafe-eval' concessions: Next.js dev tooling and hydration need inline
// scripts without a nonce setup; styles are injected inline by Tailwind/Framer Motion.
// connect-src is limited to self + the Triplet API. No third-party origins.
// emrldtp.cc is the Travelpayouts Drive affiliate-attribution script (required for
// the affiliate marker to earn commission). Nothing else third-party is allowed.
// Scheme-less so its follow-up chunk requests work on http in local dev; on an
// https deployment the browser only allows https for it anyway.
const contentSecurityPolicy = [
  "default-src 'self'",
  `connect-src 'self' ${apiBaseUrl} emrldtp.cc`,
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' emrldtp.cc",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: emrldtp.cc",
  "font-src 'self' data:",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname, "../.."),
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
