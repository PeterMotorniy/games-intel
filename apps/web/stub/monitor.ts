import type { IncomingMessage, ServerResponse } from "node:http";

import type { components } from "../src/api/schema";

type MonitorSnapshot = components["schemas"]["MonitorSnapshot"];
type MonitorRunRead = components["schemas"]["MonitorRunRead"];

const PROCESS_DATE = "2026-09-08";
const RUN_ID = "0191c0aa-7e3b-7000-8000-000000000001";

const snapshot: MonitorSnapshot = {
  process_date: PROCESS_DATE,
  workers: [
    {
      worker_type: "catalog",
      instance_id: "catalog-a",
      status: "idle",
      current_subject: null,
      processed_ok: 4,
      processed_failed: 0,
      lag_hint: 0,
      observed_at: "2026-09-08T12:00:00Z",
      stale: false,
    },
  ],
  runs: [
    {
      id: RUN_ID,
      process_date: PROCESS_DATE,
      source: "new_releases",
      page: null,
      limit: 20,
      trigger: "manual",
      status: "running",
      discovered_count: 2,
      started_at: "2026-09-08T12:00:00Z",
      completed_at: null,
    },
  ],
  items: [
    {
      id: "0191c0aa-7e3b-7000-8000-000000000011",
      run_id: RUN_ID,
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
      run_id: RUN_ID,
      metacritic_slug: "elden-ring",
      title: "Elden Ring",
      stage: "reviews",
      status: "failed",
      error_type: "NotFoundError",
      error_message: "reviews missing",
      updated_at: "2026-09-08T12:02:00Z",
    },
    {
      id: "0191c0aa-7e3b-7000-8000-000000000013",
      run_id: RUN_ID,
      metacritic_slug: "elden-ring",
      title: "Elden Ring",
      stage: "letsplay",
      status: "degraded",
      error_type: "QuotaError",
      error_message: "YouTube quota exhausted",
      updated_at: "2026-09-08T12:02:30Z",
    },
    {
      id: "0191c0aa-7e3b-7000-8000-000000000014",
      run_id: RUN_ID,
      metacritic_slug: "sekiro",
      title: "Sekiro: Shadows Die Twice",
      stage: "cataloged",
      status: "completed",
      error_type: null,
      error_message: null,
      updated_at: "2026-09-08T12:01:20Z",
    },
    {
      id: "0191c0aa-7e3b-7000-8000-000000000015",
      run_id: RUN_ID,
      metacritic_slug: "sekiro",
      title: "Sekiro: Shadows Die Twice",
      stage: "reviews",
      status: "running",
      error_type: null,
      error_message: null,
      updated_at: "2026-09-08T12:03:00Z",
    },
  ],
  counts: [],
  cursor: {
    process_date: PROCESS_DATE,
    new_releases_done: false,
    last_browse_page: null,
  },
  scrape: {
    circuit_state: "closed",
    last_parse_error_at: null,
    parse_error_count: 0,
  },
};

export function getMonitorSnapshot(): MonitorSnapshot {
  return {
    ...snapshot,
    workers: snapshot.workers.map((row) => ({ ...row })),
    runs: snapshot.runs.map((row) => ({ ...row })),
    items: snapshot.items.map((row) => ({ ...row })),
    counts: snapshot.counts.map((row) => ({ ...row })),
    cursor: snapshot.cursor ? { ...snapshot.cursor } : null,
    scrape: { ...snapshot.scrape },
  };
}

export function acceptManualRun(): components["schemas"]["RunAcceptedResponse"] {
  const run: MonitorRunRead = {
    id: crypto.randomUUID(),
    process_date: PROCESS_DATE,
    source: "new_releases",
    page: null,
    limit: 20,
    trigger: "manual",
    status: "requested",
    discovered_count: 0,
    started_at: null,
    completed_at: null,
  };
  snapshot.runs = [...snapshot.runs, run];
  return { status: "run_accepted", process_date: PROCESS_DATE };
}

export function writeSseSnapshot(req: IncomingMessage, res: ServerResponse): void {
  res.statusCode = 200;
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Connection", "keep-alive");
  const send = (): void => {
    res.write(`data: ${JSON.stringify(getMonitorSnapshot())}\n\n`);
  };
  send();
  const timer = setInterval(send, 2000);
  req.on("close", () => {
    clearInterval(timer);
  });
}
