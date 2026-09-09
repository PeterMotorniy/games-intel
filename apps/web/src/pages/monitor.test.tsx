import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MonitorSnapshot } from "../api/types";
import { MonitorPage } from "./monitor";
import { jsonResponse, renderWithApp } from "../test/render";

const SNAPSHOT: MonitorSnapshot = {
  process_date: "2026-09-08",
  workers: [],
  runs: [
    {
      id: "0191c0aa-7e3b-7000-8000-000000000001",
      process_date: "2026-09-08",
      source: "new_releases",
      page: null,
      limit: 20,
      trigger: "manual",
      status: "running",
      discovered_count: 1,
      started_at: "2026-09-08T12:00:00Z",
      completed_at: null,
    },
  ],
  items: [
    {
      id: "0191c0aa-7e3b-7000-8000-000000000011",
      run_id: "0191c0aa-7e3b-7000-8000-000000000001",
      metacritic_slug: "elden-ring",
      title: "Elden Ring",
      stage: "cataloged",
      status: "completed",
      error_type: null,
      error_message: null,
      updated_at: "2026-09-08T12:01:00Z",
    },
    {
      id: "0191c0aa-7e3b-7000-8000-000000000012",
      run_id: "0191c0aa-7e3b-7000-8000-000000000001",
      metacritic_slug: "elden-ring",
      title: "Elden Ring",
      stage: "reviews",
      status: "failed",
      error_type: "NotFoundError",
      error_message: "reviews missing",
      updated_at: "2026-09-08T12:02:00Z",
    },
  ],
  counts: [],
  cursor: null,
  scrape: {
    circuit_state: "closed",
    last_parse_error_at: null,
    parse_error_count: 0,
  },
};

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  url: string;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }

  emit(data: MonitorSnapshot): void {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

function mockFetch(
  handler: (url: URL, init: RequestInit | undefined) => Promise<Response> | Response,
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
      return Promise.resolve(handler(url, init));
    }),
  );
}

afterEach(() => {
  FakeEventSource.instances = [];
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MonitorPage", () => {
  it("renders a run graph without replica ids and shows task errors on click", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    mockFetch(() => jsonResponse(SNAPSHOT));
    const user = userEvent.setup();
    renderWithApp(<MonitorPage />);
    expect(await screen.findByRole("heading", { name: /Manual run/ })).toBeInTheDocument();
    expect(screen.getByText("Step 1")).toBeInTheDocument();
    expect(screen.getByText("Step 2")).toBeInTheDocument();
    expect(screen.getByText("then")).toBeInTheDocument();
    expect(screen.getByText("then each game")).toBeInTheDocument();
    expect(screen.getByText("Collect Metacritic cards", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Elden Ring" })).toHaveAttribute("href", "/games/elden-ring");
    expect(screen.getByText(/8 Sep/)).toBeInTheDocument();
    expect(screen.getByText(/\d{2}:\d{2}:\d{2}/)).toBeInTheDocument();
    expect(screen.queryByText(/browse,/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/started \d/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/Finished in/).length).toBeGreaterThan(0);
    expect(screen.queryByText("catalog-a")).not.toBeInTheDocument();
    expect(screen.queryByText("Day cursor")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Collect reviews, Failed/i }));
    expect(await screen.findByText("reviews missing")).toBeInTheDocument();
    expect(screen.getByText("NotFoundError")).toBeInTheDocument();
  });

  it("explains every task status", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    mockFetch(() => jsonResponse(SNAPSHOT));
    renderWithApp(<MonitorPage />);
    expect(await screen.findByRole("heading", { name: "Task statuses" })).toBeInTheDocument();
    expect(screen.getByText(/Stopped with an error/)).toBeInTheDocument();
    expect(screen.getByText(/Finished with partial data/)).toBeInTheDocument();
  });

  it("disables the run button while POST is in-flight and toasts 202", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const user = userEvent.setup();
    let finishPost: ((value: Response) => void) | undefined;
    mockFetch((_url, init) => {
      if (init?.method === "POST") {
        return new Promise<Response>((resolve) => {
          finishPost = resolve;
        });
      }
      return jsonResponse(SNAPSHOT);
    });
    renderWithApp(<MonitorPage />);
    const button = await screen.findByRole("button", { name: "Run now" });
    await user.click(button);
    expect(button).toBeDisabled();
    expect(finishPost).toBeDefined();
    finishPost?.(await jsonResponse({ status: "run_accepted", process_date: "2026-09-08" }, 202));
    expect(await screen.findByRole("status")).toHaveTextContent("Run accepted");
    await waitFor(() => expect(button).toBeEnabled());
  });

  it("applies SSE frames without a second GET", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    mockFetch(() => jsonResponse(SNAPSHOT));
    renderWithApp(<MonitorPage />);
    expect(await screen.findByRole("heading", { name: /Manual run/ })).toBeInTheDocument();
    const source = FakeEventSource.instances[0];
    expect(source).toBeDefined();
    source.emit({
      ...SNAPSHOT,
      items: [
        ...SNAPSHOT.items,
        {
          id: "0191c0aa-7e3b-7000-8000-000000000013",
          run_id: SNAPSHOT.runs[0].id,
          metacritic_slug: "elden-ring",
          title: "Elden Ring",
          stage: "letsplay",
          status: "running",
          error_type: null,
          error_message: null,
          updated_at: "2026-09-08T12:03:00Z",
        },
      ],
    });
    expect(await screen.findByRole("button", { name: /Collect let's play, Running/i })).toBeInTheDocument();
    const gets = vi.mocked(fetch).mock.calls.filter(([, init]) => (init?.method ?? "GET") !== "POST");
    expect(gets).toHaveLength(1);
  });
});
