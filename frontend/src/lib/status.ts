import { JobStatus } from "@/types/api";

export const TERMINAL_JOB_STATUSES = new Set<JobStatus>([
  "done",
  "failed",
  "cancelled",
]);

export const ACTIVE_JOB_STATUSES = new Set<JobStatus>([
  "pending",
  "downloading",
  "extracting",
  "transcribing",
  "cutting",
  "cropping",
  "generating_metadata",
]);

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Menunggu",
  downloading: "Mengunduh YouTube",
  extracting: "Ekstrak audio",
  transcribing: "Transkripsi",
  cutting: "Potong klip",
  cropping: "Reframe & style",
  generating_metadata: "Metadata",
  done: "Selesai",
  failed: "Gagal",
  cancelled: "Dibatalkan",
};

export const JOB_STATUS_TONES: Record<JobStatus, string> = {
  pending: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-400/30 dark:bg-slate-400/10 dark:text-slate-200",
  downloading: "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-400/30 dark:bg-sky-400/10 dark:text-sky-200",
  extracting: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/30 dark:bg-blue-400/10 dark:text-blue-200",
  transcribing: "border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-400/30 dark:bg-cyan-400/10 dark:text-cyan-200",
  cutting: "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-400/30 dark:bg-indigo-400/10 dark:text-indigo-200",
  cropping: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-400/30 dark:bg-violet-400/10 dark:text-violet-200",
  generating_metadata: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-400/30 dark:bg-fuchsia-400/10 dark:text-fuchsia-200",
  done: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-200",
  failed: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-200",
  cancelled: "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-400/30 dark:bg-zinc-400/10 dark:text-zinc-200",
};

export function isTerminalJobStatus(status: JobStatus | undefined): boolean {
  return !!status && TERMINAL_JOB_STATUSES.has(status);
}

export function isActiveJobStatus(status: JobStatus | undefined): boolean {
  return !!status && ACTIVE_JOB_STATUSES.has(status);
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatSeconds(value: number): string {
  const minutes = Math.floor(value / 60);
  const seconds = Math.max(0, Math.round(value - minutes * 60));
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatTimeEstimate(value: number | null | undefined): string {
  const seconds = Math.max(0, Math.round(value || 0));
  if (seconds < 5) return "sebentar lagi";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  if (hours > 0) return `${hours}j ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${remainder}s`;
  return `${remainder}s`;
}

export function formatDuration(start: number, end: number): string {
  return `${Math.max(0, end - start).toFixed(1)}s`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
