import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Triplet Editorial Instrument" palette, now theme-aware. Tokens resolve
        // to CSS variables defined in globals.css (dark default, light override).
        // Alpha-capable tokens use the RGB-channel form so `/opacity` still works.
        ink: {
          DEFAULT: "rgb(var(--ink) / <alpha-value>)", // page base
          soft: "rgb(var(--ink-soft) / <alpha-value>)", // surface
          raised: "rgb(var(--ink-raised) / <alpha-value>)", // card surface
          deep: "rgb(var(--deep) / <alpha-value>)",
        },
        panel: "rgb(var(--panel) / <alpha-value>)",
        lifted: "rgb(var(--lifted) / <alpha-value>)",
        line: "var(--line)", // hairline rule (baked alpha)
        mist: "rgb(var(--mist) / <alpha-value>)", // muted / secondary text
        cloud: "rgb(var(--cloud) / <alpha-value>)", // primary text
        mint: {
          DEFAULT: "rgb(var(--mint) / <alpha-value>)", // actions, FitScore
          soft: "var(--mint-soft)",
          ink: "rgb(var(--mint-ink) / <alpha-value>)", // text on solid mint
        },
        sky: {
          DEFAULT: "rgb(var(--sky) / <alpha-value>)",
          soft: "var(--sky-soft)",
        },
        coral: {
          DEFAULT: "rgb(var(--coral) / <alpha-value>)", // prices only
          soft: "var(--coral-soft)",
        },
        gold: "rgb(var(--gold) / <alpha-value>)", // DealScore only
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Hanken Grotesk", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["var(--font-display)", "Bricolage Grotesque", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      letterSpacing: {
        label: "0.12em", // ui-label-caps
      },
      // The design system rejects material elevation: hierarchy comes from
      // hairlines and surface steps. Shadow tokens stay defined so existing
      // markup keeps compiling, but they render nothing.
      boxShadow: {
        deal: "none",
        lift: "none",
        glow: "none",
      },
      borderRadius: {
        card: "0",
      },
      animation: {
        "fade-up": "fade-up 0.6s ease both",
        "route-dash": "route-dash 2.4s linear infinite",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(14px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "route-dash": {
          to: { strokeDashoffset: "-24" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
