import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SimilarList } from "./SimilarList";
import { renderWithApp } from "../test/render";
import { READY_COLLECTION } from "../lib/collection";

describe("SimilarList", () => {
  it("links to other games and drops self", () => {
    renderWithApp(
      <SimilarList
        currentSlug="elden-ring"
        collection={READY_COLLECTION}
        items={[
          { metacritic_slug: "elden-ring", title: "Elden Ring", score: 1, rank: 1 },
          { metacritic_slug: "sekiro", title: "Sekiro: Shadows Die Twice", score: 0.87, rank: 2 },
        ]}
      />,
    );
    expect(screen.queryByRole("link", { name: "Elden Ring" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sekiro: Shadows Die Twice" })).toHaveAttribute(
      "href",
      "/games/sekiro",
    );
  });

  it("falls back to the slug when a similar title is missing", () => {
    renderWithApp(
      <SimilarList
        currentSlug="valheim"
        collection={READY_COLLECTION}
        items={[{ metacritic_slug: "blood-of-dawnwalker", title: " ", score: 0.4, rank: 1 }]}
      />,
    );
    expect(screen.getByRole("link", { name: "Blood Of Dawnwalker" })).toHaveAttribute(
      "href",
      "/games/blood-of-dawnwalker",
    );
  });

  it("shows an idle graphic when similar games have not been scored", () => {
    renderWithApp(
      <SimilarList
        currentSlug="animal-well"
        items={[]}
        collection={{ status: "idle", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("Similar games have not been scored yet")).toBeInTheDocument();
  });
});
