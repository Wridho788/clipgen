import { useEffect, useState } from "react";
import { JobResponse } from "@/types/api";
import { formatTimeEstimate, JOB_STATUS_LABELS, JOB_STATUS_TONES } from "@/lib/status";
import { useNow } from "@/hooks/useNow";

export function JobProgressBar({ job }: { job: JobResponse }) {
  const now = useNow();
  const [snapshotAt, setSnapshotAt] = useState(() => Date.now());
  const isFailed = job.status === "failed";
  const isDone = job.status === "done";
  const isCancelled = job.status === "cancelled";
  const elapsedSinceSnapshot = Math.max(0, (now - snapshotAt) / 1000);
  const currentStageEta = Math.max(0, job.current_stage_eta_seconds - elapsedSinceSnapshot);
  const overallEta = Math.max(0, job.overall_eta_seconds - elapsedSinceSnapshot);

  useEffect(() => {
    setSnapshotAt(Date.now());
  }, [job.current_stage_eta_seconds, job.id, job.overall_eta_seconds, job.progress, job.status, job.updated_at]);

  return (
    <section className="clipgen-panel p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <span className={`inline-flex border px-2 py-1 text-xs font-medium ${JOB_STATUS_TONES[job.status]}`}>
            {JOB_STATUS_LABELS[job.status] || job.status}
          </span>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Job {job.id.slice(0, 8)}</p>
        </div>
        <span className="text-2xl font-semibold tabular-nums text-slate-950 dark:text-slate-50">{job.progress}%</span>
      </div>

      <div className="h-2 w-full overflow-hidden bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-2 transition-all duration-500 ${
            isFailed
              ? "bg-rose-500"
              : isDone
                ? "bg-emerald-500"
                : isCancelled
                  ? "bg-zinc-400"
                  : "bg-cyan-400"
          }`}
          style={{ width: `${job.progress}%` }}
        />
      </div>

      {!isFailed && !isDone && !isCancelled && (
        <div className="mt-3 grid gap-1 border-t border-slate-100 pt-3 text-sm dark:border-slate-800 sm:grid-cols-2">
          <p className="text-slate-600 dark:text-slate-300">
            Sisa tahap ini: <span className="font-medium text-slate-950 dark:text-slate-50">{formatEta(currentStageEta)}</span>
          </p>
          <p className="text-slate-600 dark:text-slate-300 sm:text-right">
            Estimasi total: <span className="font-medium text-slate-950 dark:text-slate-50">{formatEta(overallEta)}</span>
          </p>
        </div>
      )}

      {isFailed && job.error_message && (
        <p className="mt-3 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {job.error_message}
        </p>
      )}
    </section>
  );
}

function formatEta(value: number): string {
  return value > 0 ? formatTimeEstimate(value) : "Sedang dihitung";
}
