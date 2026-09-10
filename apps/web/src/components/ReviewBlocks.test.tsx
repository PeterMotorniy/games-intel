import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { GameCard } from "../api/types";
import { LetsPlayBlock } from "./LetsPlayBlock";
import { ReviewBlock } from "./ReviewBlock";
import { CollectionNotice } from "./CollectionNotice";
import { renderWithApp } from "../test/render";
import { READY_COLLECTION, READY_HYDRATION } from "../lib/collection";

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
  metascore: 96,
  userscore: 7.8,
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
  hydration: READY_HYDRATION,
};

describe("partial hydration blocks", () => {
  it("renders review copy when summaries exist", () => {
    renderWithApp(
      <ReviewBlock
        heading="Critic reviews"
        headingId="critic-reviews"
        topic="Critic reviews"
        summary={FULL.critic}
        collection={READY_COLLECTION}
      />,
    );
    expect(screen.getByText("Great combat.")).toBeInTheDocument();
    expect(screen.getByText("combat")).toBeInTheDocument();
  });

  it("shows an idle graphic when reviews have not been collected", () => {
    renderWithApp(
      <ReviewBlock
        heading="Player reviews"
        headingId="user-reviews"
        topic="Player reviews"
        summary={null}
        collection={{ status: "idle", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("Player reviews not collected yet")).toBeInTheDocument();
    expect(screen.queryByText("Collecting reviews.")).not.toBeInTheDocument();
  });

  it("shows a loading graphic while reviews are in flight", () => {
    renderWithApp(
      <ReviewBlock
        heading="Player reviews"
        headingId="user-reviews"
        topic="Player reviews"
        summary={null}
        collection={{ status: "loading", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("Collecting player reviews")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  it("shows an empty graphic when the source had no reviews", () => {
    renderWithApp(
      <ReviewBlock
        heading="Player reviews"
        headingId="user-reviews"
        topic="Player reviews"
        summary={{ likes: [], dislikes: [], summary: "" }}
        collection={{ status: "empty", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("No player reviews on Metacritic")).toBeInTheDocument();
  });

  it("shows an error graphic when review collection failed", () => {
    renderWithApp(
      <CollectionNotice kind="error" title="Could not collect player reviews" detail="sidecar timeout" />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Could not collect player reviews");
    expect(screen.getByText("sidecar timeout")).toBeInTheDocument();
  });

  it("explains letsplay statuses without failing", () => {
    renderWithApp(
      <LetsPlayBlock
        letsplay={{ status: "no_video" }}
        collection={{ status: "empty", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("No let's play was found on YouTube")).toBeInTheDocument();
    renderWithApp(
      <LetsPlayBlock
        letsplay={{ status: "transcript_unavailable", video_url: "https://youtu.be/x" }}
        collection={{ status: "empty", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("The video has no usable transcript")).toBeInTheDocument();
    renderWithApp(
      <LetsPlayBlock
        letsplay={{ status: "quota_exceeded" }}
        collection={{ status: "error", error_type: null, error_message: null }}
      />,
    );
    expect(screen.getByText("Could not collect let's play")).toBeInTheDocument();
  });
});
