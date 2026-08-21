"use client";

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Cpu, Database, HardDrive, Server } from "lucide-react";
import { api } from "@/lib/api";
import { formatFileSize } from "@/lib/status";

export function SystemStatusBar() {
  const { data: metrics } = useQuery({
    queryKey: ["system-metrics"],
    queryFn: () => api.getSystemMetrics(),
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });
  const { data: release } = useQuery({
    queryKey: ["release-info"],
    queryFn: () => api.getReleaseInfo(),
    staleTime: 60_000,
  });

  if (!metrics && !release) {
    return null;
  }

  const storageTotal = metrics
    ? metrics.storage_bytes.uploads + metrics.storage_bytes.clips + metrics.storage_bytes.temp
    : 0;
  const workerRunning = metrics?.queue.worker_running;
  const currentJobId = metrics?.queue.current_job_id;
  const currentJobLabel = currentJobId ? `Job ${currentJobId.slice(0, 8)}` : "Siap";
  const queuedLabel = `${metrics?.queue.queue_size ?? 0} siap`;
  const cancelledQueued = metrics?.queue.cancelled_in_queue ?? 0;

  return (
    <section className="grid gap-2 text-xs text-slate-600 dark:text-slate-300 sm:grid-cols-2 lg:grid-cols-5">
      <StatusItem
        icon={<Server className="h-3.5 w-3.5" />}
        label="Release"
        value={release ? `v${release.version}` : "Memuat"}
      />
      <StatusItem
        icon={<Activity className="h-3.5 w-3.5" />}
        label="Worker"
        value={workerRunning ? currentJobLabel : "Tidak aktif"}
        tone={workerRunning ? "ok" : "warn"}
      />
      <StatusItem
        icon={<Database className="h-3.5 w-3.5" />}
        label="Queue"
        value={cancelledQueued ? `${queuedLabel} · ${cancelledQueued} batal` : queuedLabel}
      />
      <StatusItem
        icon={<HardDrive className="h-3.5 w-3.5" />}
        label="Storage"
        value={formatFileSize(storageTotal)}
      />
      <StatusItem
        icon={<Cpu className="h-3.5 w-3.5" />}
        label="Akselerasi"
        value={release?.acceleration?.label ?? "Memeriksa"}
        tone={release?.acceleration?.gpu_compatible ? "ok" : "neutral"}
      />
    </section>
  );
}

function StatusItem({
  icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: "neutral" | "ok" | "warn";
}) {
  const toneClass =
    tone === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-200"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200"
        : "border-slate-200 bg-white text-slate-700 dark:border-slate-800 dark:bg-slate-950/80 dark:text-slate-300";

  return (
    <div className={`flex min-h-10 items-center justify-between gap-3 border px-3 py-2 ${toneClass}`}>
      <div className="flex min-w-0 items-center gap-2">
        {icon}
        <span className="truncate">{label}</span>
      </div>
      <span className="shrink-0 font-medium">{value}</span>
    </div>
  );
}
