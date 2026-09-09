import { describe, expect, it } from "vitest";

import { queryKeys } from "./query-keys";

describe("queryKeys", () => {
  it("includes list filters in the games key", () => {
    expect(
      queryKeys.games({
        q: "ring",
        platform: "ps5",
        sort: "metascore",
        order: "desc",
        page: 1,
        page_size: 20,
      }),
    ).toEqual([
      "games",
      {
        q: "ring",
        platform: "ps5",
        sort: "metascore",
        order: "desc",
        page: 1,
        page_size: 20,
      },
    ]);
    expect(queryKeys.game("elden-ring")).toEqual(["game", "elden-ring"]);
    expect(queryKeys.monitor()).toEqual(["monitor"]);
  });
});
