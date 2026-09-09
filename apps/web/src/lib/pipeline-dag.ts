import type { MonitorItemRead, MonitorRunRead } from "../api/types";

export type PipelineTaskStatus =
  | "requested"
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "degraded";

export type PipelineTaskKind = "run" | "catalog" | "reviews" | "letsplay" | "similar";

export type TaskError = {
  slug: string;
  title: string | null;
  errorType: string | null;
  errorMessage: string | null;
};

export type PipelineTask = {
  id: string;
  kind: PipelineTaskKind;
  label: string;
  status: PipelineTaskStatus;
  startedAt: string | null;
  endedAt: string | null;
  errors: TaskError[];
  slug?: string;
  title?: string | null;
};

export type PipelineGameBranch = {
  slug: string;
  title: string | null;
  tasks: PipelineTask[];
};

export type PipelineRunGraph = {
  run: MonitorRunRead;
  runTask: PipelineTask;
  catalogTask: PipelineTask;
  games: PipelineGameBranch[];
};

export const DOWNSTREAM_STAGES = ["reviews", "letsplay", "similar"] as const;

export const STAGE_LABEL: Record<(typeof DOWNSTREAM_STAGES)[number], string> = {
  reviews: "Collect reviews",
  letsplay: "Collect let's play",
  similar: "Find similar games",
};

const CATALOG_STAGES = new Set(["discovered", "cataloged"]);

export function rollupStatus(statuses: PipelineTaskStatus[]): PipelineTaskStatus {
  if (statuses.length === 0) {
    return "pending";
  }
  const set = new Set(statuses);
  if (set.has("running")) {
    return "running";
  }
  if (set.has("pending") && (set.has("completed") || set.has("failed") || set.has("degraded"))) {
    return "running";
  }
  if (set.has("failed")) {
    return "failed";
  }
  if (set.has("degraded")) {
    return "degraded";
  }
  if (set.has("pending") || set.has("requested")) {
    return "pending";
  }
  return "completed";
}

function isRunIdSlug(runId: string, slug: string): boolean {
  return slug === runId;
}

function hasStoredError(item: MonitorItemRead): boolean {
  return (
    item.status === "failed" ||
    item.status === "degraded" ||
    Boolean(item.error_type || item.error_message)
  );
}

function toTaskError(item: MonitorItemRead, runId: string): TaskError {
  return {
    slug: isRunIdSlug(runId, item.metacritic_slug) ? "" : item.metacritic_slug,
    title: item.title ?? null,
    errorType: item.error_type ?? null,
    errorMessage: item.error_message ?? null,
  };
}

function itemErrors(items: MonitorItemRead[], runId: string): TaskError[] {
  const gameErrors = items.filter((item) => !isRunIdSlug(runId, item.metacritic_slug) && hasStoredError(item));
  if (gameErrors.length > 0) {
    return gameErrors.map((item) => toTaskError(item, runId));
  }
  return items.filter((item) => isRunIdSlug(runId, item.metacritic_slug) && hasStoredError(item)).map((item) => toTaskError(item, runId));
}

function uniqueSlugs(items: MonitorItemRead[], runId: string): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const item of items) {
    if (isRunIdSlug(runId, item.metacritic_slug) || seen.has(item.metacritic_slug)) {
      continue;
    }
    seen.add(item.metacritic_slug);
    ordered.push(item.metacritic_slug);
  }
  return ordered;
}

function earliest(values: string[]): string | null {
  if (values.length === 0) {
    return null;
  }
  return [...values].sort()[0] ?? null;
}

function latest(values: string[]): string | null {
  if (values.length === 0) {
    return null;
  }
  return [...values].sort()[values.length - 1] ?? null;
}

export function runPageNumber(run: MonitorRunRead): number {
  return run.page ?? 0;
}

export function runGraphTitle(run: MonitorRunRead): string {
  const trigger = run.trigger === "manual" ? "Manual" : "Scheduled";
  return `${trigger} run page ${runPageNumber(run)}`;
}

function idleDownstreamBranch(run: MonitorRunRead, catalog: PipelineTask): PipelineGameBranch {
  const catalogTerminal =
    catalog.status === "completed" || catalog.status === "failed" || catalog.status === "degraded";
  const status: PipelineTaskStatus = catalogTerminal ? "completed" : "pending";
  return {
    slug: "",
    title: null,
    tasks: DOWNSTREAM_STAGES.map((stage) => ({
      id: `${run.id}:_:${stage}`,
      kind: stage,
      label: STAGE_LABEL[stage],
      status,
      startedAt: catalog.startedAt,
      endedAt: status === "completed" ? catalog.endedAt : null,
      errors: [],
    })),
  };
}

function catalogStatusForRun(run: MonitorRunRead, catalogItems: MonitorItemRead[], slugs: string[]): PipelineTaskStatus {
  if (catalogItems.length === 0) {
    if (run.status === "failed") {
      return "failed";
    }
    if (run.status === "completed") {
      return "completed";
    }
    if (run.status === "running") {
      return "running";
    }
    return "pending";
  }
  const pageFailed = catalogItems.some(
    (item) =>
      isRunIdSlug(run.id, item.metacritic_slug) &&
      (item.status === "failed" || item.status === "degraded" || Boolean(item.error_type || item.error_message)),
  );
  const statuses: PipelineTaskStatus[] = catalogItems
    .filter((item) => !isRunIdSlug(run.id, item.metacritic_slug))
    .map((item) => item.status);
  const cataloged = new Set(
    catalogItems
      .filter((item) => item.stage === "cataloged" && !isRunIdSlug(run.id, item.metacritic_slug))
      .map((item) => item.metacritic_slug),
  );
  for (const slug of slugs) {
    if (!cataloged.has(slug)) {
      const discovered = catalogItems.find(
        (item) => item.metacritic_slug === slug && item.stage === "discovered" && item.status === "completed",
      );
      if (discovered) {
        statuses.push(pageFailed || run.status === "failed" ? "failed" : "pending");
      }
    }
  }
  return rollupStatus(statuses);
}

export function buildRunGraph(run: MonitorRunRead, items: MonitorItemRead[]): PipelineRunGraph {
  const mine = items.filter((item) => item.run_id === run.id);
  const catalogItems = mine.filter((item) => CATALOG_STAGES.has(item.stage));
  const slugs = uniqueSlugs(mine, run.id);
  const bySlug = new Map<string, MonitorItemRead[]>();
  for (const item of mine) {
    const list = bySlug.get(item.metacritic_slug) ?? [];
    list.push(item);
    bySlug.set(item.metacritic_slug, list);
  }

  const completedCards = catalogItems.filter(
    (item) => item.stage === "cataloged" && item.status === "completed",
  ).length;
  const expectedCards = Math.max(run.discovered_count, slugs.length);
  const emptyCompleted =
    catalogItems.length === 0 && run.status === "completed" && run.discovered_count === 0;
  const catalogCount =
    expectedCards > 0
      ? `${completedCards} of ${expectedCards} games`
      : emptyCompleted
        ? "no new games"
        : null;

  const runTask: PipelineTask = {
    id: `${run.id}:run`,
    kind: "run",
    label: "Start pipeline",
    status: run.status === "requested" ? "requested" : run.status,
    startedAt: run.started_at ?? null,
    endedAt: run.completed_at ?? null,
    errors:
      run.status === "failed"
        ? [
            {
              slug: "",
              title: null,
              errorType: "run_failed",
              errorMessage: "The pipeline run failed before all tasks finished.",
            },
          ]
        : [],
  };

  const catalogStatus = catalogStatusForRun(run, catalogItems, slugs);
  const catalogRunning = catalogStatus === "running" || catalogStatus === "pending" || catalogStatus === "requested";
  const catalogTask: PipelineTask = {
    id: `${run.id}:catalog`,
    kind: "catalog",
    label: catalogCount ? `Collect Metacritic cards (${catalogCount})` : "Collect Metacritic cards",
    status: catalogStatus,
    startedAt: run.started_at ?? earliest(catalogItems.map((item) => item.updated_at)),
    endedAt: catalogRunning
      ? null
      : latest(catalogItems.map((item) => item.updated_at)) ?? run.completed_at ?? null,
    errors: itemErrors(catalogItems, run.id),
  };

  const games: PipelineGameBranch[] = slugs
    .map((slug) => {
      const rows = bySlug.get(slug) ?? [];
      const title = rows.find((row) => row.title)?.title ?? null;
      const catalogedAt =
        rows.find((row) => row.stage === "cataloged" && row.status === "completed")?.updated_at ?? null;
      const tasks: PipelineTask[] = DOWNSTREAM_STAGES.map((stage) => {
        const item = rows.find((row) => row.stage === stage);
        if (item) {
          const terminal = item.status === "completed" || item.status === "failed" || item.status === "degraded";
          return {
            id: `${run.id}:${slug}:${stage}`,
            kind: stage,
            label: STAGE_LABEL[stage],
            status: item.status,
            startedAt: item.status === "running" ? item.updated_at : catalogedAt ?? item.updated_at,
            endedAt: terminal ? item.updated_at : null,
            errors: itemErrors([item], run.id),
            slug,
            title,
          };
        }
        return {
          id: `${run.id}:${slug}:${stage}`,
          kind: stage,
          label: STAGE_LABEL[stage],
          status: "pending",
          startedAt: null,
          endedAt: null,
          errors: [],
          slug,
          title,
        };
      });
      return { slug, title, tasks };
    })
    .sort((a, b) => (a.title ?? a.slug).localeCompare(b.title ?? b.slug));

  return {
    run,
    runTask,
    catalogTask,
    games: games.length > 0 ? games : [idleDownstreamBranch(run, catalogTask)],
  };
}

export function sortRunsNewestFirst(runs: MonitorRunRead[]): MonitorRunRead[] {
  return [...runs].sort((a, b) => {
    const aTime = a.started_at ?? a.completed_at ?? "";
    const bTime = b.started_at ?? b.completed_at ?? "";
    if (aTime !== bTime) {
      return bTime.localeCompare(aTime);
    }
    return b.id.localeCompare(a.id);
  });
}
