import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { GameListItem } from "../api/types";
import { GameCard } from "./GameCard";
import { renderWithApp } from "../test/render";
import { READY_COLLECTION } from "../lib/collection";

const GAME: GameListItem = {
  metacritic_slug: "elden-ring",
  title: "Elden Ring",
  cover_url: "/api/v1/media/covers/elden-ring",
  developer: "FromSoftware",
  metascore: 96,
  userscore: 7.8,
  platforms: ["ps5", "pc"],
  updated_at: "2026-09-08T10:00:00Z",
  catalog_collection: READY_COLLECTION,
};

describe("GameCard", () => {
  it("renders cover, title, developer, metascore and platform chips", () => {
    renderWithApp(<GameCard game={GAME} />);
    expect(screen.getByRole("img", { name: "Elden Ring" })).toHaveAttribute(
      "src",
      "/api/v1/media/covers/elden-ring",
    );
    expect(screen.getByRole("heading", { name: "Elden Ring" })).toBeInTheDocument();
    expect(screen.getByText("FromSoftware")).toBeInTheDocument();
    expect(screen.getByText("96")).toBeInTheDocument();
    expect(screen.getByText("7.8")).toBeInTheDocument();
    expect(screen.getByText("ps5")).toBeInTheDocument();
    expect(screen.getByText("pc")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Elden Ring/ })).toHaveAttribute(
      "href",
      "/games/elden-ring",
    );
  });
});
