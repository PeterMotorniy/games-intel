import { describe, expect, it } from "vitest";

import { collectionTitle, fieldState, hydrationIsLoading, READY_HYDRATION } from "./collection";

describe("fieldState", () => {
  it("keeps ready values even when the stage is still idle", () => {
    expect(fieldState(true, { status: "idle" })).toBe("ready");
  });

  it("treats a finished collection without a value as empty", () => {
    expect(fieldState(false, { status: "ready" })).toBe("empty");
  });

  it("uses the collection status when the value is missing", () => {
    expect(fieldState(false, { status: "loading" })).toBe("loading");
    expect(fieldState(false, { status: "empty" })).toBe("empty");
    expect(fieldState(false, { status: "error" })).toBe("error");
    expect(fieldState(false, undefined)).toBe("idle");
  });
});

describe("hydrationIsLoading", () => {
  it("detects a loading stage", () => {
    expect(hydrationIsLoading(READY_HYDRATION)).toBe(false);
    expect(
      hydrationIsLoading({
        ...READY_HYDRATION,
        critic: { status: "loading", error_type: null, error_message: null },
      }),
    ).toBe(true);
  });
});

describe("collectionTitle", () => {
  it("names the four collection outcomes", () => {
    expect(collectionTitle("idle", "Player reviews")).toMatch(/not collected yet/i);
    expect(collectionTitle("loading", "Player reviews")).toMatch(/collecting/i);
    expect(collectionTitle("empty", "Player reviews")).toMatch(/no player reviews found/i);
    expect(collectionTitle("error", "Player reviews")).toMatch(/could not collect/i);
  });
});
