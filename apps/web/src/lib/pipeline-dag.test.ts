import { describe, expect, it } from "vitest";

import type { MonitorItemRead, MonitorRunRead } from "../api/types";
import { buildRunGraph, rollupStatus, runGraphTitle, sortRunsNewestFirst } from "./pipeline-dag";

const RUN: MonitorRunRead = {
  id: "0191c0aa-7e3b-7000-8000-000000000001",
  process_date: "2026-09-08",
  source: "new_releases",
  page: null,
  limit: 20,
  trigger: "manual",
  status: "running",
  discovered_count: 2,
  started_at: "2026-09-08T12:00:00Z",
  completed_at: null,
};

function item(
  overrides: Partial<MonitorItemRead> & Pick<MonitorItemRead, "metacritic_slug" | "stage" | "status">,
): MonitorItemRead {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    run_id: RUN.id,
    title: null,
    error_type: null,
    error_message: null,
    updated_at: "2026-09-08T12:01:00Z",
    ...overrides,
  };
}

describe("rollupStatus", () => {
  it("treats mixed completed and pending as running", () => {
    expect(rollupStatus(["completed", "pending"])).toBe("running");
  });

  it("prefers failed over degraded when nothing is running", () => {
    expect(rollupStatus(["completed", "failed", "degraded"])).toBe("failed");
  });
});

describe("buildRunGraph", () => {
  it("fans out per-game review and lets play tasks from the catalog node", () => {
    const graph = buildRunGraph(RUN, [
      item({
        metacritic_slug: "elden-ring",
        title: "Elden Ring",
        stage: "discovered",
        status: "completed",
      }),
      item({
        metacritic_slug: "elden-ring",
        title: "Elden Ring",
        stage: "cataloged",
        status: "completed",
      }),
      item({
        metacritic_slug: "sekiro",
        title: "Sekiro",
        stage: "discovered",
        status: "completed",
      }),
      item({
        metacritic_slug: "sekiro",
        title: "Sekiro",
        stage: "cataloged",
        status: "completed",
      }),
      item({
        metacritic_slug: "elden-ring",
        stage: "reviews",
        status: "failed",
        error_type: "NotFoundError",
        error_message: "reviews missing",
      }),
      item({
        metacritic_slug: "elden-ring",
        stage: "letsplay",
        status: "degraded",
        error_type: "QuotaError",
        error_message: "quota",
      }),
    ]);
    expect(graph.runTask.label).toBe("Start pipeline");
    expect(graph.catalogTask.kind).toBe("catalog");
    expect(graph.catalogTask.status).toBe("completed");
    expect(graph.games).toHaveLength(2);
    const elden = graph.games.find((row) => row.slug === "elden-ring");
    expect(elden?.tasks.map((task) => task.kind)).toEqual(["reviews", "letsplay", "similar"]);
    expect(elden?.tasks[0]?.status).toBe("failed");
    expect(elden?.tasks[0]?.errors[0]?.errorMessage).toBe("reviews missing");
    expect(elden?.tasks[1]?.status).toBe("degraded");
    expect(elden?.tasks[2]?.status).toBe("pending");
  });

  it("marks catalog as failed when a card scrape failed", () => {
    const graph = buildRunGraph(RUN, [
      item({ metacritic_slug: "broken", stage: "cataloged", status: "failed", error_message: "404" }),
      item({ metacritic_slug: "ok", stage: "cataloged", status: "completed" }),
    ]);
    expect(graph.catalogTask.status).toBe("failed");
    expect(graph.catalogTask.errors).toHaveLength(1);
  });

  it("does not keep catalog running after a page-level fail left games only discovered", () => {
    const graph = buildRunGraph(
      { ...RUN, status: "completed", discovered_count: 2, completed_at: "2026-09-08T12:05:00Z" },
      [
        item({
          metacritic_slug: "elden-ring",
          title: "Elden Ring",
          stage: "discovered",
          status: "completed",
        }),
        item({
          metacritic_slug: "sekiro",
          title: "Sekiro",
          stage: "discovered",
          status: "completed",
        }),
        item({
          metacritic_slug: RUN.id,
          stage: "cataloged",
          status: "failed",
          error_type: "TransientError",
          error_message: "sidecar request timed out",
        }),
      ],
    );
    expect(graph.catalogTask.status).toBe("failed");
    expect(graph.catalogTask.endedAt).not.toBeNull();
    expect(graph.games.map((row) => row.slug).sort()).toEqual(["elden-ring", "sekiro"]);
    expect(graph.catalogTask.errors.some((error) => error.errorType === "TransientError")).toBe(true);
  });

  it("surfaces errors stored on running items", () => {
    const graph = buildRunGraph(RUN, [
      item({
        metacritic_slug: "elden-ring",
        stage: "reviews",
        status: "running",
        error_type: "TransientError",
        error_message: "sidecar request timed out",
      }),
    ]);
    const reviews = graph.games[0]?.tasks.find((task) => task.kind === "reviews");
    expect(reviews?.errors[0]?.errorMessage).toBe("sidecar request timed out");
  });

  it("keeps review and lets play tasks when a completed run found no new games", () => {
    const graph = buildRunGraph(
      { ...RUN, status: "completed", discovered_count: 0, completed_at: "2026-09-08T12:00:03Z" },
      [],
    );
    expect(graph.catalogTask.status).toBe("completed");
    expect(graph.catalogTask.label).toContain("no new games");
    expect(graph.catalogTask.endedAt).toBe("2026-09-08T12:00:03Z");
    expect(graph.games).toHaveLength(1);
    expect(graph.games[0]?.slug).toBe("");
    expect(graph.games[0]?.tasks.map((task) => [task.kind, task.status])).toEqual([
      ["reviews", "completed"],
      ["letsplay", "completed"],
      ["similar", "completed"],
    ]);
  });
});

describe("runGraphTitle", () => {
  it("labels new_releases as page 0", () => {
    expect(runGraphTitle(RUN)).toBe("Manual run page 0");
  });

  it("labels browse runs with the listing page", () => {
    expect(runGraphTitle({ ...RUN, source: "browse", page: 1, trigger: "cron" })).toBe(
      "Scheduled run page 1",
    );
  });
});

describe("sortRunsNewestFirst", () => {
  it("orders by started_at descending", () => {
    const older = { ...RUN, id: "a", started_at: "2026-09-08T11:00:00Z" };
    const newer = { ...RUN, id: "b", started_at: "2026-09-08T13:00:00Z" };
    expect(sortRunsNewestFirst([older, newer]).map((row) => row.id)).toEqual(["b", "a"]);
  });
});
