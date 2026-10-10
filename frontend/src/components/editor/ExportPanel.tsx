"use client";

import { AlertTriangle, CheckCircle2, Download, Loader2, RefreshCw, Wand2 } from "lucide-react";

import { api } from "@/lib/api";
import { ClipResponse } from "@/types/api";

type ExportPanelProps = {
  clip: ClipResponse;
  hasUnsavedChanges: boolean;
  invalidReason: string | null;
  isSubmitting: boolean;
  submitError: string | null;
  onRender: () => void;
};

const CHECK_LABELS: Record<string, string> = {
  exists: "File ada",
  non_empty: "Tidak kosong",
  probeable: "Terbaca ffprobe",
  dimensions: "Dimensi sesuai preset",
  duration: "Durasi sesuai trim",
  audio: "Audio sesuai pengaturan",
  decodable: "Frame awal bisa di-decode",
};

export function ExportPanel({ clip, hasUnsavedChanges, invalidReason, isSubmitting, submitError, onRender }: ExportPanelProps) {
  const rendering = clip.status === "processing";
  const report = clip.render_report;
  const stale = clip.render_stale || hasUnsavedChanges;
  const canDownload = !!clip.file_path && !rendering;

  return (
    <section aria-label="Export" className="space-y-3 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Export MP4</p>
          <p className="text-xs text-slate-500 dark:text-slate-400" data-testid="render-state">
            {rendering
              ? "Merender revisi tersimpan…"
              : stale
                ? "File belum mengikuti edit terbaru — render ulang sebelum download."
                : clip.file_path
                  ? `File sesuai edit revisi ${clip.rendered_revision ?? 0}.`
                  : "Belum ada file render."}
          </p>
        </div>
        <button
          type="button"
          onClick={onRender}
          disabled={rendering || isSubmitting || !!invalidReason}
          title={invalidReason || undefined}
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {rendering || isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : stale ? <Wand2 className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
          {rendering ? "Merender…" : stale ? "Render edit" : "Render ulang"}
        </button>
      </div>

      {(submitError || clip.render_error_message) && !rendering && (
        <div role="alert" className="flex items-start gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p>{submitError || clip.render_error_message}</p>
            {clip.render_error_code && !submitError && <p className="mt-0.5 font-mono text-[11px] text-rose-500">{clip.render_error_code}</p>}
            {clip.file_path && <p className="mt-1 text-xs">File sebelumnya tetap tersedia dan edit tidak hilang.</p>}
          </div>
        </div>
      )}

      {report && (
        <details className="text-xs text-slate-600 dark:text-slate-300" open={!report.validation.ok}>
          <summary className="flex cursor-pointer items-center gap-1.5">
            {report.validation.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />}
            <span data-testid="validation-summary">
              {report.validation.ok ? "Lolos validasi" : "Validasi gagal"} · {report.validation.width}×{report.validation.height} ·{" "}
              {report.validation.duration_seconds?.toFixed(2)} dtk · audio {report.validation.has_audio ? "ada" : "tidak ada"} · {report.captions_rendered} caption
            </span>
          </summary>
          <ul className="mt-2 grid gap-1 sm:grid-cols-2">
            {Object.entries(report.validation.checks).map(([key, ok]) => (
              <li key={key} className="flex items-center gap-1.5">
                <span aria-hidden>{ok ? "✓" : "✗"}</span>
                {CHECK_LABELS[key] || key}
                <span className="sr-only">{ok ? "lolos" : "gagal"}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">
            Render {report.render_seconds}s dengan {report.encoder} · {(report.validation.size_bytes / 1_048_576).toFixed(1)} MB
          </p>
        </details>
      )}

      {canDownload && (
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={api.getClipDownloadUrl(clip.id)}
            download
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${stale ? "border border-amber-300 bg-amber-50 text-amber-900" : "bg-slate-950 text-white dark:bg-cyan-300 dark:text-slate-950"}`}
          >
            <Download className="h-4 w-4" />
            {stale ? "Download file lama" : "Download MP4"}
          </a>
          <span className="text-[11px] text-slate-500">Disimpan di storage lokal ClipGen (backend/storage/clips) dan diunduh ke folder Download browser.</span>
        </div>
      )}
    </section>
  );
}
