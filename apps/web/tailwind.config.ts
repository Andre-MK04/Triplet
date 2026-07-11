import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Triplet Editorial Instrument" palette (Stitch design system).
        // Depth comes from the surface scale + hairlines, not shadows/blur.
        ink: {
          DEFAULT: "#0b1117", // page base
          soft: "#0e141a", // surface
          raised: "#161c22", // surface-container-low
          deep: "#090f15", // surface-container-lowest
        },
        panel: "#1a2027", // surface-container
        lifted: "#252b31", // surface-container-high
        line: "rgba(232, 240, 244, 0.15)", // hairline rule
        mist: "#93a6b4", // muted steel: secondary text
        cloud: "#e8f0f4", // paper white: primary text
        mint: {
          DEFAULT: "#7ddfc3", // actions, FitScore
          soft: "rgba(125, 223, 195, 0.12)",
          ink: "#00382c", // text on solid mint
        },
        sky: {
          DEFAULT: "#8ec5ff",
          soft: "rgba(142, 197, 255, 0.12)",
        },
        coral: {
          DEFAULT: "#ff9a78", // prices only
          soft: "rgba(255, 154, 120, 0.14)",
        },
        gold: "#ffd08a", // DealScore only
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
