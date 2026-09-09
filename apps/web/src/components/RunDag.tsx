import { useEffect, useState } from "react";
import { Link } from "react-router";

import { displayTitle, formatDateTime, formatTaskTiming } from "../lib/format";
import type { PipelineGameBranch, PipelineRunGraph, PipelineTask } from "../lib/pipeline-dag";
import { TASK_STATUS_LABEL } from "../lib/status";

type RunDagProps = {
  graph: PipelineRunGraph;
  onSelectTask: (task: PipelineTask) => void;
};

function useNow(enabled: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) {
      return;
    }
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [enabled]);
  return now;
}

function TaskNode({
  task,
  nowMs,
  onSelect,
}: {
  task: PipelineTask;
  nowMs: number;
  onSelect: (task: PipelineTask) => void;
}) {
  const failed = task.status === "failed" || task.status === "degraded";
  const timing = formatTaskTiming(task.status, task.startedAt, task.endedAt, nowMs);
  return (
    <button
      type="button"
      className={`dag-node dag-node--${task.kind} dag-node--${task.status}`}
      onClick={() => onSelect(task)}
      aria-label={`${task.label}, ${TASK_STATUS_LABEL[task.status]}, ${timing}${failed ? ". Open error details." : ""}`}
    >
      <span className="dag-node__title">{task.label}</span>
      <span className={`status-badge status-badge--${task.status}`}>{TASK_STATUS_LABEL[task.status]}</span>
      <span className="dag-node__time">{timing}</span>
    </button>
  );
}

function GameBranch({
  branch,
  step,
  nowMs,
  onSelect,
}: {
  branch: PipelineGameBranch;
  step: string;
  nowMs: number;
  onSelect: (task: PipelineTask) => void;
}) {
  const name = displayTitle(branch.title, branch.slug);
  return (
    <li className="dag-game">
      <p className="dag-stage__label">{step}</p>
      <p className="dag-game__title">
        <Link to={`/games/${branch.slug}`}>{name}</Link>
      </p>
      <ul className="dag-game__fork">
        {branch.tasks.map((task) => (
          <li key={task.id}>
            <TaskNode task={task} nowMs={nowMs} onSelect={onSelect} />
          </li>
        ))}
      </ul>
    </li>
  );
}

export function RunDag({ graph, onSelectTask }: RunDagProps) {
  const trigger = graph.run.trigger === "manual" ? "Manual" : "Scheduled";
  const live =
    graph.runTask.status === "running" ||
    graph.catalogTask.status === "running" ||
    graph.games.some((branch) => branch.tasks.some((task) => task.status === "running"));
  const nowMs = useNow(live);
  return (
    <section className="panel run-graph" aria-labelledby={`run-${graph.run.id}-heading`}>
      <header className="run-graph__header">
        <h2 id={`run-${graph.run.id}-heading`}>
          {trigger} run
          {graph.run.page != null
            ? ` page ${graph.run.page}`
            : graph.run.source === "new_releases"
              ? " · new releases"
              : ""}
        </h2>
        <p className="muted">
          {graph.run.started_at ? formatDateTime(graph.run.started_at) : "Not started"}
        </p>
      </header>
      <div className="dag" role="group" aria-label={`Pipeline graph for ${trigger.toLowerCase()} run`}>
        <div className="dag-stage">
          <p className="dag-stage__label">Step 1</p>
          <TaskNode task={graph.runTask} nowMs={nowMs} onSelect={onSelectTask} />
        </div>
        <p className="dag-then">then</p>
        <div className="dag-stage dag-stage--catalog">
          <p className="dag-stage__label">Step 2</p>
          <TaskNode task={graph.catalogTask} nowMs={nowMs} onSelect={onSelectTask} />
          {graph.games.length > 0 ? (
            <div className="dag-fanout">
              <p className="dag-then dag-then--down">then each game</p>
              <ol className="dag-games">
                {graph.games.map((branch, index) => (
                  <GameBranch
                    key={branch.slug}
                    branch={branch}
                    step={`Step 3.${index + 1}`}
                    nowMs={nowMs}
                    onSelect={onSelectTask}
                  />
                ))}
              </ol>
            </div>
          ) : (
            <p className="muted dag-empty">
              {graph.run.status === "completed" && graph.run.discovered_count === 0
                ? "No new games this run. They were already collected today or the listing was empty."
                : "Waiting for game cards from this run."}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
