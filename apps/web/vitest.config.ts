import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Pure logic only for now: sorting, price presentation, URL handling.
    // Component rendering would need jsdom and a heavier setup, and these are
    // the modules where a silent regression would actually mislead a traveller.
    include: ["lib/**/*.test.ts", "app/**/*.test.ts"],
    environment: "node",
  },
});
