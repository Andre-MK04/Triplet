import type { NextConfig } from "next";
import path from "node:path";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

// When set (production), API calls go to a same-origin path (/backend/…) and Next
// proxies them here server-side. First-party cookies: browsers' third-party cookie
// blocking between vercel.app and railway.app can't break auth this way.
const apiProxyTarget = process.env.API_PROXY_TARGET;

// Triplet loads no third-party scripts. Affiliate commission is earned through
// the `marker` query parameter that the API puts into every Aviasales booking
// URL it builds (see providers/travelpayouts/affiliate_links.py), so the
// Travelpayouts Drive script was never what carried attribution — it was
// third-party behavioural JS on every page for nothing, with the power to
// rewrite outbound links. It is gone, and so is its CSP origin.
//
// 'unsafe-inline' remains for the pre-paint theme script and for styles that
// Tailwind and Framer Motion inject inline. 'unsafe-eval' is development-only:
// Next.js needs it for dev tooling and React Refresh, and nothing in a
// production build does.
const isDev = process.env.NODE_ENV !== "production";

const contentSecurityPolicy = [
  "default-src 'self'",
  // A relative API base (proxy mode) is already covered by 'self'.
  `connect-src 'self'${apiBaseUrl.startsWith("http") ? " " + apiBaseUrl : ""}`,
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
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
  async rewrites() {
    if (!apiProxyTarget) return [];
    return [
      {
        source: "/backend/:path*",
        destination: `${apiProxyTarget.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
};

export default nextConfig;
