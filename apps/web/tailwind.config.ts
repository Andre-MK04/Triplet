import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101820",
        panel: "#162029",
        line: "#2a3844",
        mint: "#7ddfc3",
        coral: "#ff9a78",
      },
      boxShadow: {
        deal: "0 20px 60px rgba(0, 0, 0, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
