"use client";

import { useEffect, useState } from "react";

import { applyTheme, readThemePreference, storeThemePreference, type ThemePreference } from "../lib/theme";

const ORDER: ThemePreference[] = ["light", "dark", "system"];

const ICONS: Record<ThemePreference, React.ReactNode> = {
  light: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  dark: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  ),
  system: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="4" width="18" height="12" rx="1" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  ),
};

const LABELS: Record<ThemePreference, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePreference>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setPref(readThemePreference());
    setMounted(true);
  }, []);

  // When following the system, react to OS theme changes live.
  useEffect(() => {
    if (pref !== "system") return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [pref]);

  function cycle() {
    const next = ORDER[(ORDER.indexOf(pref) + 1) % ORDER.length];
    setPref(next);
    storeThemePreference(next);
    applyTheme(next);
  }

  // Render a stable placeholder until mounted to avoid hydration mismatch.
  const current: ThemePreference = mounted ? pref : "dark";
  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={`Theme: ${LABELS[current]}. Click to change.`}
      title={`Theme: ${LABELS[current]}`}
      className="inline-flex h-8 w-8 items-center justify-center border border-line text-mist transition-colors hover:border-mint/60 hover:text-mint"
    >
      {ICONS[current]}
    </button>
  );
}
