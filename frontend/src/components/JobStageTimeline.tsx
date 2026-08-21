"use client";

import { useEffect, useState } from "react";
import { Check, Circle, Loader2, X } from "lucide-react";
import { JobResponse, JobStatus } from "@/types/api";
import { formatTimeEstimate, JOB_STATUS_LABELS } from "@/lib/status";
import { useNow } from "@/hooks/useNow";

const STAGE_ORDER: JobStatus[] = [
  "downloading",
  "analyzing_intro",
  "extracting",
  "transcribing",
  "detecting",
  "cutting",
  "cropping",
  "subtitling",
  "generating_metadata",
];

export function JobStageTimeline({ job }: { job: JobResponse }) {
  const now = useNow();
  const [snapshotAt, setSnapshotAt] = useState(() => Date.now());
  const stages = getStages(job);
  const activeIndex = stages.indexOf(job.status);
  const isFailed = job.status === "failed";
  const isCancelled = job.status === "cancelled";
  const currentStageEta = Math.max(0, job.current_stage_eta_seconds - Math.max(0, (now - snapshotAt) / 1000));
  const activityAt = job.heartbeat_at || job.updated_at;

  useEffect(() => {
    setSnapshotAt(Date.now());
  }, [job.current_stage_eta_seconds, job.id, job.progress, job.status, job.updated_at]);

  return (
    <section className="clipgen-panel p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Pipeline</h2>
        <span className="text-xs text-slate-500 dark:text-slate-400">Aktivitas {new Date(activityAt).toLocaleTimeString("id-ID")}</span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {stages.map((stage, index) => {
          const isPast = activeIndex > index || job.status === "done";
          const isCurrent = activeIndex === index && !isFailed && !isCancelled;

          return (
            <div
              key={stage}
              className={`flex min-h-11 items-center gap-2 border px-3 py-2 text-sm ${
                isPast
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-200"
                  : isCurrent
                    ? "border-cyan-300 bg-slate-950 text-white shadow-[0_0_20px_rgba(34,211,238,0.2)] dark:border-cyan-400"
                    : "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400"
              }`}
            >
              {isPast ? (
                <Check className="h-4 w-4 shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
              ) : (
                <Circle className="h-4 w-4 shrink-0" />
              )}
              <div className="min-w-0">
                <p className="truncate">{JOB_STATUS_LABELS[stage]}</p>
                <p className={`text-xs ${isCurrent ? "text-slate-300" : isPast ? "text-emerald-700" : "text-slate-400"}`}>
                  {stageTimingLabel(job, stage, isCurrent, isPast, currentStageEta)}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {(isFailed || isCancelled) && (
        <div className="mt-3 flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <X className="h-4 w-4" />
          {isCancelled ? "Job dibatalkan." : job.error_message || "Job berhenti sebelum selesai."}
        </div>
      )}
    </section>
  );
}

function getStages(job: JobResponse): JobStatus[] {
  const activeStages = STAGE_ORDER.filter(
    (stage) => job.stage_estimates?.[stage] !== undefined || job.status === stage
  );
  if (activeStages.length === 0) {
    return [
      "pending",
      ...(job.source_type === "youtube_url" ? (["downloading"] as JobStatus[]) : []),
      "extracting",
      "transcribing",
      "detecting",
      "cutting",
      "generating_metadata",
      "done",
    ];
  }
  return ["pending", ...activeStages, "done"];
}

function stageTimingLabel(
  job: JobResponse,
  stage: JobStatus,
  isCurrent: boolean,
  isPast: boolean,
  currentStageEta: number,
): string {
  if (isCurrent && currentStageEta > 0) {
    return `Sisa ${formatTimeEstimate(currentStageEta)}`;
  }
  if (isPast && job.stage_metrics?.[stage] !== undefined) {
    return `Selesai ${formatTimeEstimate(job.stage_metrics[stage])}`;
  }
  const estimate = job.stage_estimates?.[stage];
  return estimate ? `Est. ${formatTimeEstimate(estimate)}` : "";
}
