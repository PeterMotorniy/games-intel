import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { fetchMonitor, monitorStreamUrl, startRun } from "../api/client";
import { queryKeys } from "../api/query-keys";
import { PageState } from "../components/PageState";
import { RunDag } from "../components/RunDag";
import { StatusLegend } from "../components/StatusLegend";
import { TaskDetailDialog } from "../components/TaskDetailDialog";
import type { MonitorSnapshot } from "../api/types";
import { buildRunGraph, sortRunsNewestFirst, type PipelineTask } from "../lib/pipeline-dag";

export function MonitorPage() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<PipelineTask | null>(null);
  const monitorQuery = useQuery({
    queryKey: queryKeys.monitor(),
    queryFn: fetchMonitor,
    staleTime: 0,
  });

  useMonitorStream(true);

  const runMutation = useMutation({
    mutationFn: startRun,
    onSuccess: (accepted) => {
      setToast(`Run accepted for ${accepted.process_date}`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.monitor() });
    },
    onError: (error) => {
      setToast(error instanceof Error ? error.message : "Could not start a run");
    },
  });

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const snapshot = monitorQuery.data;
  const graphs = useMemo(() => {
    if (!snapshot) {
      return [];
    }
    return sortRunsNewestFirst(snapshot.runs).map((run) => buildRunGraph(run, snapshot.items));
  }, [snapshot]);

  return (
    <div className="page page--wide">
      <header className="page-header monitor-header">
        <div>
          <h1>Pipeline monitor</h1>
          <p className="lede">Each run is a graph of catalog, reviews, let's plays, and similar games.</p>
        </div>
        <button
          type="button"
          className="button button--accent"
          disabled={runMutation.isPending}
          onClick={() => runMutation.mutate()}
        >
          {runMutation.isPending ? "Starting..." : "Run now"}
        </button>
      </header>

      <div className="toast-live" aria-live="polite" aria-atomic="true">
        {toast ? (
          <p className="toast" role="status">
            {toast}
          </p>
        ) : null}
      </div>

      {monitorQuery.isPending ? <PageState kind="loading" title="Loading monitor..." /> : null}
      {monitorQuery.isError ? (
        <PageState
          kind="error"
          title="Could not load the monitor"
          detail={monitorQuery.error instanceof Error ? monitorQuery.error.message : null}
          onRetry={() => void monitorQuery.refetch()}
        />
      ) : null}

      {snapshot ? (
        <>
          <StatusLegend />
          {graphs.length === 0 ? (
            <PageState kind="empty" title="No pipeline runs yet">
              <p className="page-state__detail">Start a run to see the task graph.</p>
            </PageState>
          ) : (
            graphs.map((graph) => (
              <RunDag key={graph.run.id} graph={graph} onSelectTask={setSelectedTask} />
            ))
          )}
        </>
      ) : null}

      <TaskDetailDialog task={selectedTask} onClose={() => setSelectedTask(null)} />
    </div>
  );
}

function useMonitorStream(enabled: boolean) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") {
      return;
    }
    let retry = 0;
    let timer: number | undefined;
    let source: EventSource | null = null;
    const connect = () => {
      source = new EventSource(monitorStreamUrl());
      source.onmessage = (event) => {
        retry = 0;
        try {
          const next = JSON.parse(event.data) as MonitorSnapshot;
          queryClient.setQueryData(queryKeys.monitor(), next);
        } catch {
          // Ignore a malformed frame; snapshot query remains the source of truth.
        }
      };
      source.onerror = () => {
        source?.close();
        source = null;
        const delay = Math.min(1000 * 2 ** retry, 15000);
        retry += 1;
        timer = window.setTimeout(connect, delay);
      };
    };
    connect();
    return () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
      source?.close();
    };
  }, [enabled, queryClient]);
}
