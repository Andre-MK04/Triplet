import { describe, expect, it } from "vitest";

import { shouldSearchAutocomplete } from "./autocomplete";

describe("autocomplete committed labels", () => {
  it("does not re-search the city label that was just selected", () => {
    expect(shouldSearchAutocomplete("Copenhagen, Denmark", "Copenhagen, Denmark", 2, true)).toBe(false);
  });

  it("searches again once the traveller edits the selected label", () => {
    expect(shouldSearchAutocomplete("Copen", "Copenhagen, Denmark", 2, true)).toBe(true);
  });
});
