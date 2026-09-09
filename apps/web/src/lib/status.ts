import type { PipelineTaskStatus } from "./pipeline-dag";

export const TASK_STATUS_LABEL: Record<PipelineTaskStatus, string> = {
  requested: "Requested",
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  degraded: "Degraded",
};

export const TASK_STATUS_HELP: Record<PipelineTaskStatus, string> = {
  requested: "The run was accepted and is waiting for a worker.",
  pending: "Queued. This task has not started yet.",
  running: "A worker is processing this task now.",
  completed: "Finished successfully.",
  degraded: "Finished with partial data. Click the task for details.",
  failed: "Stopped with an error. Click the task for details.",
};
