import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router";

import type { GameCard } from "../api/types";
import { GamePage } from "./game";
import { jsonResponse, renderWithApp } from "../test/render";

const CARD: GameCard = {
  metacritic_slug: "elden-ring",
  title: "Elden Ring",
  cover_url: "/api/v1/media/covers/elden-ring",
  developer: "FromSoftware",
  publisher: "Bandai Namco",
  description: "An open-world action RPG set in the Lands Between.",
  video_url: "https://www.youtube.com/watch?v=E3Huy2cdih0",
  genres: ["Action", "RPG"],
  release_date: "2022-02-25",
  platforms: [{ platform_code: "ps5", metascore: 96, userscore: 7.8 }],
  critic: { likes: ["combat"], dislikes: ["performance"], summary: "Great combat." },
  user: { likes: ["exploration"], dislikes: ["difficulty"], summary: "Harsh but fair." },
  letsplay: {
    status: "ok",
    video_url: "https://www.youtube.com/watch?v=letsplay-elden",
    video_title: "Elden Ring Let's Play",
    view_count: 10,
    conclusion: "Блогер хвалит исследование мира.",
    highlights: ["open world"],
  },
  similar: [{ metacritic_slug: "sekiro", title: "Sekiro: Shadows Die Twice", score: 0.87, rank: 1 }],
};

const SEKIRO: GameCard = {
  ...CARD,
  metacritic_slug: "sekiro",
  title: "Sekiro: Shadows Die Twice",
  video_url: null,
  similar: [{ metacritic_slug: "elden-ring", title: "Elden Ring", score: 0.87, rank: 1 }],
};

function mockCards(cards: Record<string, GameCard>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
      const match = /\/games\/([^/?]+)$/.exec(url.pathname);
      const slug = match?.[1] ?? "";
      const card = cards[slug];
      if (!card) {
        return jsonResponse({ title: "Not Found", status: 404, detail: "missing" }, 404);
      }
      return jsonResponse(card);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderGame(route: string) {
  return renderWithApp(
    <Routes>
      <Route path="/games/:slug" element={<GamePage />} />
    </Routes>,
    { route },
  );
}

describe("GamePage", () => {
  it("renders required fields from a full fixture", async () => {
    mockCards({ "elden-ring": CARD });
    renderGame("/games/elden-ring");
    expect(await screen.findByRole("heading", { name: "Elden Ring" })).toBeInTheDocument();
    expect(screen.getByText("FromSoftware")).toBeInTheDocument();
    expect(screen.getByText("An open-world action RPG set in the Lands Between.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Watch trailer" })).toHaveAttribute(
      "href",
      CARD.video_url ?? "",
    );
    expect(screen.getByText("Great combat.")).toBeInTheDocument();
    expect(screen.getByText("Harsh but fair.")).toBeInTheDocument();
    expect(screen.getByText("Блогер хвалит исследование мира.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sekiro: Shadows Die Twice" })).toHaveAttribute(
      "href",
      "/games/sekiro",
    );
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("RPG")).toBeInTheDocument();
    expect(screen.getByText(/2022/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Metacritic" })).toHaveAttribute(
      "href",
      "https://www.metacritic.com/game/elden-ring/",
    );
  });

  it("hides the trailer block when video_url is null", async () => {
    mockCards({ sekiro: SEKIRO });
    renderGame("/games/sekiro");
    expect(await screen.findByRole("heading", { name: "Sekiro: Shadows Die Twice" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Watch trailer" })).not.toBeInTheDocument();
  });

  it("shows card error state", async () => {
    mockCards({});
    renderGame("/games/missing");
    expect(await screen.findByRole("alert")).toHaveTextContent("Game not found");
  });

  it("navigates to a similar game", async () => {
    const user = userEvent.setup();
    mockCards({ "elden-ring": CARD, sekiro: SEKIRO });
    renderGame("/games/elden-ring");
    await user.click(await screen.findByRole("link", { name: "Sekiro: Shadows Die Twice" }));
    expect(await screen.findByRole("heading", { name: "Sekiro: Shadows Die Twice" })).toBeInTheDocument();
  });
});
