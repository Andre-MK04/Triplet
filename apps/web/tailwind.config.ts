import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark premium travel palette
        ink: {
          DEFAULT: "#0b1117",
          soft: "#101821",
          raised: "#151f2a",
        },
        panel: "#162029",
        line: "rgba(148, 184, 210, 0.14)",
        mist: "#93a6b4",
        cloud: "#e8f0f4",
        mint: {
          DEFAULT: "#7ddfc3",
          soft: "rgba(125, 223, 195, 0.14)",
        },
        sky: {
          DEFAULT: "#8ec5ff",
          soft: "rgba(142, 197, 255, 0.14)",
        },
        coral: {
          DEFAULT: "#ff9a78",
          soft: "rgba(255, 154, 120, 0.16)",
        },
        gold: "#ffd08a",
      },
      fontFamily: {
        sans: [
          "Inter",
          "SF Pro Text",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          "Inter",
          "SF Pro Display",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
      boxShadow: {
        deal: "0 20px 60px rgba(0, 0, 0, 0.28)",
        lift: "0 24px 70px rgba(0, 0, 0, 0.45)",
        glow: "0 0 0 1px rgba(125, 223, 195, 0.25), 0 12px 40px rgba(125, 223, 195, 0.12)",
      },
      borderRadius: {
        card: "1.25rem",
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
