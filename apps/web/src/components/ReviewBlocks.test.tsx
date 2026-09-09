import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { GameCard } from "../api/types";
import { LetsPlayBlock } from "./LetsPlayBlock";
import { ReviewBlock } from "./ReviewBlock";
import { renderWithApp } from "../test/render";

const FULL: GameCard = {
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

describe("partial hydration blocks", () => {
  it("renders review copy when summaries exist", () => {
    renderWithApp(<ReviewBlock heading="Critic reviews" headingId="critic-reviews" summary={FULL.critic} />);
    expect(screen.getByText("Great combat.")).toBeInTheDocument();
    expect(screen.getByText("combat")).toBeInTheDocument();
  });

  it("shows collecting copy when reviews are missing", () => {
    renderWithApp(<ReviewBlock heading="Player reviews" headingId="user-reviews" summary={null} />);
    expect(screen.getByText("Collecting reviews.")).toBeInTheDocument();
  });

  it("shows an empty state when the summarizer stored no copy", () => {
    renderWithApp(
      <ReviewBlock
        heading="Player reviews"
        headingId="user-reviews"
        summary={{ likes: [], dislikes: [], summary: "" }}
      />,
    );
    expect(screen.getByText("No reviews yet.")).toBeInTheDocument();
    expect(screen.queryByText("Collecting reviews.")).not.toBeInTheDocument();
  });

  it("explains letsplay statuses without failing", () => {
    renderWithApp(<LetsPlayBlock letsplay={{ status: "no_video" }} />);
    expect(screen.getByText("No let's play was found on YouTube.")).toBeInTheDocument();
    renderWithApp(<LetsPlayBlock letsplay={{ status: "transcript_unavailable" }} />);
    expect(screen.getByText(/transcript is unavailable/)).toBeInTheDocument();
    renderWithApp(<LetsPlayBlock letsplay={{ status: "quota_exceeded" }} />);
    expect(screen.getByText(/YouTube quota is exhausted/)).toBeInTheDocument();
  });
});
