import { useEffect, useId, useRef } from "react";

import { formatTaskTiming } from "../lib/format";
import type { PipelineTask } from "../lib/pipeline-dag";
import { TASK_STATUS_LABEL } from "../lib/status";

type TaskDetailDialogProps = {
  task: PipelineTask | null;
  onClose: () => void;
};

export function TaskDetailDialog({ task, onClose }: TaskDetailDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const node = dialogRef.current;
    if (!node) {
      return;
    }
    if (task) {
      if (!node.open) {
        try {
          node.showModal();
        } catch {
          node.setAttribute("open", "");
        }
      }
    } else if (node.open) {
      try {
        node.close();
      } catch {
        node.removeAttribute("open");
      }
    }
  }, [task]);

  return (
    <dialog
      ref={dialogRef}
      className="task-dialog"
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          onClose();
        }
      }}
    >
      {task ? (
        <div className="task-dialog__body">
          <h2 id={titleId}>{task.label}</h2>
          {task.title ? <p className="task-dialog__game">{task.title}</p> : null}
          <p>
            <span className={`status-badge status-badge--${task.status}`}>{TASK_STATUS_LABEL[task.status]}</span>
          </p>
          <p className="muted">{formatTaskTiming(task.status, task.startedAt, task.endedAt, Date.now())}</p>
          {task.errors.length > 0 ? (
            <ul className="task-dialog__errors">
              {task.errors.map((error, index) => (
                <li key={`${error.slug}:${error.errorType}:${index}`}>
                  {error.title || error.slug ? (
                    <strong>{error.title || error.slug}: </strong>
                  ) : null}
                  {error.errorType ? <span className="chip chip--error">{error.errorType}</span> : null}{" "}
                  {error.errorMessage ?? "No error details were stored."}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No error details for this task.</p>
          )}
          <form method="dialog">
            <button type="submit" className="button">
              Close
            </button>
          </form>
        </div>
      ) : null}
    </dialog>
  );
}
