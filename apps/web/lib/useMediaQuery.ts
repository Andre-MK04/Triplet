"use client";

import { useEffect, useState } from "react";

/**
 * Whether a CSS media query currently matches.
 *
 * This exists so JavaScript can agree with the stylesheet about what is on
 * screen. A `hidden lg:flex` wrapper stops a decorative component from being
 * *seen* on a phone, but it does not stop React from mounting it or a dynamic
 * import from fetching its chunk — so the work still happens, and the bytes are
 * still downloaded, for something nobody can look at.
 *
 * Returns false during server rendering and on the first client render, then
 * corrects itself. Components gated on this must therefore be safe to appear a
 * moment late, which is true of decoration and false of content.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;

    const list = window.matchMedia(query);
    setMatches(list.matches);

    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);
    list.addEventListener("change", onChange);
    return () => list.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/**
 * Tailwind's `lg` breakpoint, as a query.
 *
 * Kept next to the hook rather than inline at call sites so that a component
 * gated in JavaScript and hidden in CSS cannot drift apart into disagreeing
 * about where the boundary is.
 */
export const LG_BREAKPOINT = "(min-width: 1024px)";

/**
 * Whether the visitor has asked for less motion.
 *
 * Decorative animation is the first thing that should go when someone has said
 * they do not want it — and if the animation is the only reason a heavy library
 * is on the page, the library can go with it.
 */
export const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
