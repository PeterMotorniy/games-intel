import { TASK_STATUS_HELP, TASK_STATUS_LABEL } from "../lib/status";
import type { PipelineTaskStatus } from "../lib/pipeline-dag";

const STATUSES: PipelineTaskStatus[] = [
  "requested",
  "pending",
  "running",
  "completed",
  "degraded",
  "failed",
];

export function StatusLegend() {
  return (
    <section className="panel status-legend" aria-labelledby="status-legend-heading">
      <h2 id="status-legend-heading">Task statuses</h2>
      <ul className="status-legend__list">
        {STATUSES.map((status) => (
          <li key={status} className="status-legend__item">
            <span className={`status-badge status-badge--${status}`}>{TASK_STATUS_LABEL[status]}</span>
            <span>{TASK_STATUS_HELP[status]}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
