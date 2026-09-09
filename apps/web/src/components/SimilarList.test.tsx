import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SimilarList } from "./SimilarList";
import { renderWithApp } from "../test/render";

describe("SimilarList", () => {
  it("links to other games and drops self", () => {
    renderWithApp(
      <SimilarList
        currentSlug="elden-ring"
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
        items={[{ metacritic_slug: "blood-of-dawnwalker", title: " ", score: 0.4, rank: 1 }]}
      />,
    );
    expect(screen.getByRole("link", { name: "Blood Of Dawnwalker" })).toHaveAttribute(
      "href",
      "/games/blood-of-dawnwalker",
    );
  });

  it("shows a pending message when the list is empty", () => {
    renderWithApp(<SimilarList currentSlug="animal-well" items={[]} />);
    expect(screen.getByText("Similar games will appear after scoring.")).toBeInTheDocument();
  });
});
