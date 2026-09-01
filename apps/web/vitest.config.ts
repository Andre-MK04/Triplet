import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Pure logic and small browser-storage modules. Component rendering would
    // need a full DOM and a heavier setup; these are the modules where a silent
    // regression would actually mislead a traveller.
    include: ["lib/**/*.test.ts", "app/**/*.test.ts"],
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
  },
});
