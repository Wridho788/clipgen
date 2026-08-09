"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertCircle, ArrowRight, Clock3, RefreshCw, Search } from "lucide-react";
import { api } from "@/lib/api";
import {
  formatDateTime,
  isActiveJobStatus,
  isTerminalJobStatus,
  JOB_STATUS_LABELS,
  JOB_STATUS_TONES,
} from "@/lib/status";
import { JobResponse, JobStatus } from "@/types/api";
import { VideoUpload } from "@/components/VideoUpload";
import { SystemStatusBar } from "@/components/SystemStatusBar";
import { ThemeToggle } from "@/components/ThemeToggle";

type JobFilter = "all" | "active" | Extract<JobStatus, "done" | "failed" | "cancelled">;

const JOB_FILTERS: { value: JobFilter; label: string }[] = [
  { value: "all", label: "Semua" },
  { value: "active", label: "Aktif" },
  { value: "done", label: "Selesai" },
  { value: "failed", label: "Gagal" },
  { value: "cancelled", label: "Batal" },
];

export default function Dashboard() {
  const [filter, setFilter] = useState<JobFilter>("all");
  const { data: jobs, isLoading, isFetching, error, refetch } = useQuery<JobResponse[]>({
    queryKey: ["jobs"],
    queryFn: () => api.listJobs(),
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.some((job) => !isTerminalJobStatus(job.status)) ? 3000 : false;
    },
  });

  const filteredJobs = useMemo(() => {
    const list = jobs || [];
    if (filter === "all") return list;
    if (filter === "active") return list.filter((job) => isActiveJobStatus(job.status));
    return list.filter((job) => job.status === filter);
  }, [filter, jobs]);

  const counts = useMemo(() => {
    const list = jobs || [];
    return {
      all: list.length,
      active: list.filter((job) => isActiveJobStatus(job.status)).length,
      done: list.filter((job) => job.status === "done").length,
      failed: list.filter((job) => job.status === "failed").length,
      cancelled: list.filter((job) => job.status === "cancelled").length,
    };
  }, [jobs]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 dark:border-slate-800 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 inline-flex border border-cyan-500/30 bg-cyan-50 px-2 py-1 text-xs font-medium text-cyan-700 dark:bg-cyan-300/10 dark:text-cyan-200">
            Local clip studio
          </div>
          <h1 className="text-3xl font-semibold tracking-normal text-slate-950 dark:text-slate-50">ClipGen</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Upload, monitor, preview, dan download clip dari satu tempat.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex min-h-10 w-fit items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-cyan-300"
            title="Refresh jobs"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      <SystemStatusBar />

      <VideoUpload />

      <section className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Job History</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{filteredJobs.length} dari {jobs?.length || 0} job</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {JOB_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                className={`inline-flex min-h-9 items-center gap-2 border px-3 py-1.5 text-sm ${
                  filter === item.value
                    ? "border-slate-900 bg-slate-950 text-white dark:border-cyan-300 dark:bg-cyan-300 dark:text-slate-950"
                    : "border-slate-300 bg-white text-slate-700 hover:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300 dark:hover:border-cyan-300"
                }`}
                title={`Filter ${item.label}`}
              >
                {item.label}
                <span className={filter === item.value ? "text-slate-300 dark:text-slate-700" : "text-slate-500 dark:text-slate-400"}>
                  {counts[item.value]}
                </span>
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            <AlertCircle className="h-4 w-4" />
            {error instanceof Error ? error.message : "Gagal memuat job"}
          </div>
        )}

        {isLoading && <JobRowSkeleton />}
        {!isLoading && !error && (!jobs || jobs.length === 0) && (
          <div className="clipgen-panel px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
            Belum ada job
          </div>
        )}
        {!isLoading && !error && jobs && jobs.length > 0 && filteredJobs.length === 0 && (
          <div className="clipgen-panel flex items-center justify-center gap-2 px-4 py-8 text-sm text-slate-500 dark:text-slate-400">
            <Search className="h-4 w-4" />
            Tidak ada job untuk filter ini
          </div>
        )}

        <div className="space-y-2">
          {filteredJobs.map((job) => (
            <Link
              key={job.id}
              href={`/jobs/${job.id}`}
              className="clipgen-panel group block p-3 transition hover:border-slate-400 hover:bg-slate-50 dark:hover:border-cyan-300/60 dark:hover:bg-slate-900"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-slate-950 dark:text-slate-50">
                      {job.source_type === "youtube_url" ? "YouTube" : "Upload"} {job.id.slice(0, 8)}
                    </span>
                    <span className={`shrink-0 border px-2 py-0.5 text-xs ${JOB_STATUS_TONES[job.status]}`}>
                      {JOB_STATUS_LABELS[job.status]}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <Clock3 className="h-3.5 w-3.5" />
                    {formatDateTime(job.created_at)}
                    <span>Updated {formatDateTime(job.updated_at)}</span>
                  </div>
                  {job.error_message && (
                    <p className="mt-2 line-clamp-2 text-xs text-rose-600">{job.error_message}</p>
                  )}
                </div>
                <div className="flex min-w-24 items-center gap-3">
                  <span className="text-sm tabular-nums text-slate-600 dark:text-slate-300">{job.progress}%</span>
                  <ArrowRight className="h-4 w-4 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-slate-900 dark:group-hover:text-cyan-200" />
                </div>
              </div>
              <div className="mt-3 h-1.5 w-full bg-slate-100 dark:bg-slate-800">
                <div
                  className={`h-1.5 ${
                    job.status === "failed"
                      ? "bg-rose-500"
                      : job.status === "done"
                        ? "bg-emerald-500"
                        : job.status === "cancelled"
                          ? "bg-zinc-400"
                          : "bg-cyan-400"
                  }`}
                  style={{ width: `${job.progress}%` }}
                />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function JobRowSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((item) => (
        <div key={item} className="clipgen-panel p-3">
          <div className="h-4 w-40 animate-pulse bg-slate-200 dark:bg-slate-800" />
          <div className="mt-2 h-3 w-24 animate-pulse bg-slate-100 dark:bg-slate-900" />
        </div>
      ))}
    </div>
  );
}
