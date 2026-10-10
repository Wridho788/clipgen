"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertCircle, ArrowLeft, DownloadCloud, Loader2, OctagonX, RefreshCw, RotateCcw, ShieldCheck, Square } from "lucide-react";
import { api } from "@/lib/api";
import { CampaignBrief } from "@/types/api";
import { formatDateTime, formatTimeEstimate, isActiveJobStatus, isTerminalJobStatus } from "@/lib/status";
import { useJobStatus } from "@/hooks/useJobStatus";
import { useClips } from "@/hooks/useClips";
import { JobProgressBar } from "@/components/JobProgressBar";
import { JobStageTimeline } from "@/components/JobStageTimeline";
import { ClipCard } from "@/components/ClipCard";
import { ClipGallery } from "@/components/ClipGallery";
import { ClipEditor } from "@/components/editor/ClipEditor";
import { CopyButton } from "@/components/CopyButton";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function JobPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;
  const queryClient = useQueryClient();

  const { data: job, isLoading, error, refetch, isFetching } = useJobStatus(jobId);
  const {
    data: clips,
    isLoading: clipsLoading,
    error: clipsError,
  } = useClips(jobId, job?.status);

  const readyClips = useMemo(() => clips?.filter((clip) => clip.file_path) || [], [clips]);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const selectedClip = readyClips.find((clip) => clip.id === selectedClipId) || readyClips[0] || null;
  const campaignBrief = useMemo(() => parseCampaignBrief(job?.processing_options), [job?.processing_options]);

  const cancelJob = useMutation({
    mutationFn: () => api.cancelJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const retryJob = useMutation({
    mutationFn: () => api.retryJob(jobId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      router.push(`/jobs/${result.job_id}`);
    },
  });

  const canCancel = job && !isTerminalJobStatus(job.status);
  const canRetry = !!job && isTerminalJobStatus(job.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-violet-700 dark:text-slate-300 dark:hover:text-violet-200">
            <ArrowLeft className="h-4 w-4" />
            Kembali
          </Link>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950 dark:text-slate-50">{job?.source_name && !job.source_name.startsWith("http") ? job.source_name : `Project ${jobId.slice(0, 8)}`}</h1>
            {job && (
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Dibuat {formatDateTime(job.created_at)} · Updated {formatDateTime(job.updated_at)}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <ThemeToggle />
          <CopyButton value={jobId} label="Copy ID" copiedLabel="Copied" />
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-violet-300"
            title="Refresh job"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {canCancel && (
            <button
              type="button"
              onClick={() => cancelJob.mutate()}
              disabled={cancelJob.isPending}
              className="inline-flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 hover:border-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
              title="Cancel job"
            >
              {cancelJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              Cancel
            </button>
          )}
        </div>
      </div>

      {isLoading && <JobPageSkeleton />}
      {error && (
        <div className="flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <AlertCircle className="h-4 w-4" />
          {error instanceof Error ? error.message : "Job tidak ditemukan"}
        </div>
      )}
      {cancelJob.error && (
        <div className="flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <OctagonX className="h-4 w-4" />
          {cancelJob.error instanceof Error ? cancelJob.error.message : "Gagal cancel job"}
        </div>
      )}
      {retryJob.error && (
        <div className="flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          <OctagonX className="h-4 w-4" />
          {retryJob.error instanceof Error ? retryJob.error.message : "Gagal membuat job ulang"}
        </div>
      )}

      {job && <JobProgressBar job={job} />}
      {job && <JobStageTimeline job={job} />}

      {campaignBrief && (
        <section className="rounded-2xl border border-violet-200 bg-violet-50/70 p-4 dark:border-violet-300/20 dark:bg-violet-400/10">
          <div className="flex items-start gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-700 dark:bg-violet-300/15 dark:text-violet-200"><ShieldCheck className="h-4 w-4" /></div><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-violet-700 dark:text-violet-200">Campaign brief</p><h2 className="mt-1 font-semibold text-violet-950 dark:text-violet-50">{campaignBrief.name}</h2><p className="mt-1 text-sm text-violet-800/80 dark:text-violet-100/80">{campaignBrief.min_clip_seconds}–{campaignBrief.max_clip_seconds} detik · hook {campaignBrief.hook_max_seconds} detik · {campaignBrief.hashtags.length} hashtag wajib</p></div></div>
          {campaignBrief.required_phrases.length > 0 && <p className="mt-3 border-t border-violet-200 pt-3 text-xs text-violet-800 dark:border-violet-300/20 dark:text-violet-100">Narasi wajib: {campaignBrief.required_phrases.join(", ")}</p>}
        </section>
      )}

      {job && isActiveJobStatus(job.status) && (
        <div className="border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-800 dark:border-cyan-400/30 dark:bg-cyan-400/10 dark:text-cyan-100">
          <p>Processing sedang berjalan.</p>
          {job.status === "pending" && (
            <p className="mt-1 text-xs">
              Worker lokal memproses satu job dalam satu waktu.
              {job.queue_position !== null ? ` Posisi antrean: #${job.queue_position}.` : " Job sedang menunggu sinkronisasi antrean."}
            </p>
          )}
          {job.estimated_total_seconds >= 900 && (
            <p className="mt-1 text-xs">Video ini diperkirakan memerlukan sekitar {formatTimeEstimate(job.estimated_total_seconds)}. Proses panjang tetap dapat dibatalkan.</p>
          )}
        </div>
      )}

      {canRetry && (
        <section className="flex flex-col gap-3 border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-950 dark:text-slate-50">Proses ulang</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Buat job baru yang terhubung ke job ini tanpa mengubah hasil lama.</p>
          </div>
          <button
            type="button"
            onClick={() => retryJob.mutate()}
            disabled={retryJob.isPending}
            className="inline-flex items-center justify-center gap-2 bg-slate-950 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-cyan-300 dark:text-slate-950"
          >
            {retryJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            Proses ulang
          </button>
        </section>
      )}

      {job?.status === "done" && (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Klip</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{readyClips.length} siap dari {clips?.length || 0} clip</p>
            </div>
            <a
              href={readyClips.length > 0 ? api.getJobArchiveUrl(jobId) : undefined}
              aria-disabled={readyClips.length === 0}
              className={`inline-flex w-fit items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-cyan-300 ${readyClips.length === 0 ? "pointer-events-none cursor-not-allowed opacity-50" : ""}`}
              title="Download arsip semua clip"
            >
              <DownloadCloud className="h-4 w-4" />
              Download ZIP
            </a>
          </div>
          {clipsLoading && <ClipSkeleton />}
          {clipsError && (
            <div className="flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              <AlertCircle className="h-4 w-4" />
              {clipsError instanceof Error ? clipsError.message : "Gagal memuat klip"}
            </div>
          )}
          {!clipsLoading && !clipsError && clips?.length === 0 && (
            <div className="clipgen-panel px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
              Tidak ada klip
            </div>
          )}
          {readyClips.length > 0 && (
            <section className="rounded-3xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-900/40 sm:p-4">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2 px-1">
                <div>
                  <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">Pilih klip untuk diedit</p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Geser untuk melihat semua hasil. Detail, metadata, dan download tampil hanya untuk klip yang dipilih.</p>
                </div>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm dark:bg-slate-800 dark:text-slate-300">{readyClips.length} klip</span>
              </div>
              <ClipGallery clips={readyClips} selectedClipId={selectedClip?.id || null} onSelect={setSelectedClipId} />
            </section>
          )}
          {selectedClip && (
            <section>
              <div className="mb-3 flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-600 dark:text-violet-300">Editor klip</p><h3 className="mt-1 text-lg font-semibold text-slate-950 dark:text-slate-50">{selectedClip.title || "Klip terpilih"}</h3></div><span className="text-xs text-slate-500 dark:text-slate-400">{readyClips.findIndex((clip) => clip.id === selectedClip.id) + 1} / {readyClips.length}</span></div>
              <ClipEditor
                key={selectedClip.id}
                clip={selectedClip}
                clips={readyClips}
                sourceDurationSeconds={job.source_duration_seconds}
                onSelect={setSelectedClipId}
              />
            </section>
          )}
          {clips?.filter((clip) => clip.status === "failed").map((clip) => <ClipCard key={clip.id} clip={clip} />)}
        </div>
      )}
    </div>
  );
}

function JobPageSkeleton() {
  return (
    <div className="clipgen-panel p-4">
      <div className="h-5 w-28 animate-pulse bg-slate-200 dark:bg-slate-800" />
      <div className="mt-3 h-2 w-full animate-pulse bg-slate-100 dark:bg-slate-900" />
    </div>
  );
}

function ClipSkeleton() {
  return (
    <div className="flex gap-3 overflow-hidden">
      {[0, 1, 2, 3].map((item) => (
        <div key={item} className="w-32 shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
          <div className="aspect-[9/16] animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
          <div className="mt-2 h-3 w-20 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  );
}

function parseCampaignBrief(raw: string | null | undefined): CampaignBrief | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { campaign_brief?: CampaignBrief };
    return parsed.campaign_brief || null;
  } catch {
    return null;
  }
}
