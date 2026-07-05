"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const RouteGlobe = dynamic(() => import("./RouteGlobe"), {
  ssr: false,
  loading: () => <StaticRouteArt />,
});

/** SVG fallback: shown while the globe loads, on reduced motion, and on small screens. */
export function StaticRouteArt() {
  return (
    <svg viewBox="0 0 420 420" className="h-full w-full" role="img" aria-label="Illustration of flight routes across a globe">
      <defs>
        <radialGradient id="globe-fill" cx="38%" cy="32%">
          <stop offset="0%" stopColor="#1c2a38" />
          <stop offset="100%" stopColor="#0e1721" />
        </radialGradient>
        <linearGradient id="arc-stroke" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#7ddfc3" />
          <stop offset="100%" stopColor="#8ec5ff" />
        </linearGradient>
      </defs>
      <circle cx="210" cy="210" r="170" fill="url(#globe-fill)" stroke="rgba(148,184,210,0.25)" />
      {[0.35, 0.62, 0.85].map((factor) => (
        <ellipse
          key={factor}
          cx="210"
          cy="210"
          rx={170 * factor}
          ry={170}
          fill="none"
          stroke="rgba(148,184,210,0.12)"
        />
      ))}
      {[-45, 0, 45].map((offset) => (
        <ellipse key={offset} cx="210" cy={210 + offset} rx="168" ry={64 - Math.abs(offset) * 0.4} fill="none" stroke="rgba(148,184,210,0.12)" />
      ))}
      <path d="M120 250 Q 210 90 305 175" fill="none" stroke="url(#arc-stroke)" strokeWidth="2.5" className="route-line" />
      <path d="M150 290 Q 250 160 320 245" fill="none" stroke="url(#arc-stroke)" strokeWidth="2" className="route-line" opacity="0.7" />
      <path d="M105 200 Q 190 60 290 120" fill="none" stroke="url(#arc-stroke)" strokeWidth="1.5" className="route-line" opacity="0.5" />
      <circle cx="120" cy="250" r="6" fill="#7ddfc3" />
      <circle cx="305" cy="175" r="6" fill="#ff9a78" />
      <circle cx="150" cy="290" r="4.5" fill="#7ddfc3" opacity="0.8" />
      <circle cx="320" cy="245" r="4.5" fill="#ff9a78" opacity="0.8" />
    </svg>
  );
}

export function Hero3D() {
  const [enable3D, setEnable3D] = useState(false);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const smallScreen = window.matchMedia("(max-width: 767px)").matches;
    // Keep mobile fast and honor reduced motion: SVG art instead of WebGL.
    setEnable3D(!reducedMotion && !smallScreen);
  }, []);

  return (
    <div className="relative h-[320px] w-full sm:h-[420px] lg:h-[480px]">
      <div
        aria-hidden
        className="absolute inset-0 rounded-full bg-mint/5 blur-3xl"
        style={{ transform: "scale(0.8)" }}
      />
      {enable3D ? <RouteGlobe animate /> : <StaticRouteArt />}
    </div>
  );
}
