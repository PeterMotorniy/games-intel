import { describe, expect, it } from "vitest";

import {
  displayTitle,
  formatDate,
  formatDateTime,
  formatDuration,
  formatTaskTiming,
  metacriticGameUrl,
} from "./format";

describe("formatDate", () => {
  it("keeps the calendar date without a clock", () => {
    expect(formatDate("2026-09-09T15:00:28Z")).toMatch(/9 Sep/);
  });
});

describe("formatDateTime", () => {
  it("includes the calendar date and a clock", () => {
    const formatted = formatDateTime("2026-09-09T15:00:28Z");
    expect(formatted).toMatch(/9 Sep/);
    expect(formatted).toMatch(/2026/);
    expect(formatted).toMatch(/\d{2}:\d{2}:\d{2}/);
  });
});

describe("formatDuration", () => {
  it("formats seconds, minutes, and hours", () => {
    expect(formatDuration(4_000)).toBe("4s");
    expect(formatDuration(65_000)).toBe("1m 5s");
    expect(formatDuration(3_720_000)).toBe("1h 2m");
  });
});

describe("formatTaskTiming", () => {
  it("shows a live timer while running and a duration when finished", () => {
    const start = "2026-09-09T12:00:00.000Z";
    const now = Date.parse("2026-09-09T12:01:30.000Z");
    expect(formatTaskTiming("pending", null, null, now)).toBe("Not started");
    expect(formatTaskTiming("running", start, null, now)).toBe("Active 1m 30s");
    expect(formatTaskTiming("completed", start, "2026-09-09T12:00:12.000Z", now)).toBe("Finished in 12s");
    expect(formatTaskTiming("completed", start, null, now)).toBe("Finished");
  });
});

describe("displayTitle", () => {
  it("falls back to a readable slug when the title is empty", () => {
    expect(displayTitle("Valheim", "valheim")).toBe("Valheim");
    expect(displayTitle("  ", "elden-ring-tarnished-edition")).toBe("Elden Ring Tarnished Edition");
  });
});

describe("metacriticGameUrl", () => {
  it("uses the listing URL when present", () => {
    expect(metacriticGameUrl("valheim", "https://www.metacritic.com/game/valheim/")).toBe(
      "https://www.metacritic.com/game/valheim/",
    );
    expect(metacriticGameUrl("valheim")).toBe("https://www.metacritic.com/game/valheim/");
  });
});
