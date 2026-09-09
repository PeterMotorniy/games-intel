import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ListPage } from "./list";
import { jsonResponse, renderWithApp } from "../test/render";
import type { GameListResponse, PlatformListResponse } from "../api/types";

const EMPTY: GameListResponse = {
  items: [],
  meta: { page: 1, page_size: 20, total: 0, sort: "metascore", order: "desc" },
};

const LIST: GameListResponse = {
  items: [
    {
      metacritic_slug: "elden-ring",
      title: "Elden Ring",
      cover_url: null,
      developer: "FromSoftware",
      metascore: 96,
      userscore: 7.8,
      platforms: ["ps5"],
      updated_at: "2026-09-08T10:00:00Z",
    },
    {
      metacritic_slug: "sekiro",
      title: "Sekiro: Shadows Die Twice",
      cover_url: null,
      developer: "FromSoftware",
      metascore: 90,
      userscore: 8.4,
      platforms: ["pc"],
      updated_at: "2026-09-08T09:00:00Z",
    },
  ],
  meta: { page: 1, page_size: 20, total: 2, sort: "metascore", order: "desc" },
};

const PLATFORMS: PlatformListResponse = { items: ["pc", "ps5"] };

function mockFetch(handler: (url: URL) => Promise<Response> | Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
      return Promise.resolve(handler(url));
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ListPage", () => {
  it("shows empty state", async () => {
    mockFetch((url) => {
      if (url.pathname.endsWith("/platforms")) {
        return jsonResponse(PLATFORMS);
      }
      return jsonResponse(EMPTY);
    });
    renderWithApp(<ListPage />);
    expect(await screen.findByText("No games yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the monitor and start a run" })).toHaveAttribute(
      "href",
      "/monitor",
    );
  });

  it("shows error with retry", async () => {
    mockFetch(() => jsonResponse({ title: "Service Unavailable", status: 503, detail: "down" }, 503));
    renderWithApp(<ListPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the catalog");
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
  });

  it("refetches when search text is typed", async () => {
    const user = userEvent.setup();
    mockFetch((url) => {
      if (url.pathname.endsWith("/platforms")) {
        return jsonResponse(PLATFORMS);
      }
      if ((url.searchParams.get("q") ?? "").toLowerCase().includes("sekiro")) {
        return jsonResponse({
          ...LIST,
          items: [LIST.items[1]],
          meta: { ...LIST.meta, total: 1 },
        });
      }
      return jsonResponse(LIST);
    });
    renderWithApp(<ListPage />);
    expect(await screen.findByRole("link", { name: /Elden Ring/ })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search"), "sekiro");
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /Elden Ring/ })).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Sekiro/ })).toBeInTheDocument();
    });
  });

  it("refetches when the platform filter changes", async () => {
    const user = userEvent.setup();
    mockFetch((url) => {
      if (url.pathname.endsWith("/platforms")) {
        return jsonResponse(PLATFORMS);
      }
      if (url.searchParams.get("platform") === "ps5") {
        return jsonResponse({
          ...LIST,
          items: [LIST.items[0]],
          meta: { ...LIST.meta, total: 1 },
        });
      }
      return jsonResponse(LIST);
    });
    renderWithApp(<ListPage />);
    expect(await screen.findByRole("link", { name: /Elden Ring/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Sekiro/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "ps5" }));
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /Sekiro/ })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /Elden Ring/ })).toBeInTheDocument();
    const calls = vi.mocked(fetch).mock.calls.map(([input]) => String(input));
    expect(calls.some((url) => url.includes("platform=ps5"))).toBe(true);
  });
});
