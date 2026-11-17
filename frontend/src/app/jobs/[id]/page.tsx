"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertCircle, ArrowLeft, DownloadCloud, Loader2, OctagonX, RefreshCw, RotateCcw, ShieldCheck, Square } from "lucide-react";
import { api } from "@/lib/api";
import { CampaignBrief } from "@/types/api";
import { formatDateTime, formatTimeEstimate, isActiveJobStatus, isTerminalJobStatus, JOB_STATUS_LABELS, JOB_STATUS_TONES } from "@/lib/status";
import { useJobStatus } from "@/hooks/useJobStatus";
import { useClips } from "@/hooks/useClips";
import { JobProgressBar } from "@/components/JobProgressBar";
import { JobStageTimeline } from "@/components/JobStageTimeline";
import { ClipCard } from "@/components/ClipCard";
import { ClipGallery } from "@/components/ClipGallery";
import { ClipEditor } from "@/components/editor/ClipEditor";
import { CopyButton } from "@/components/CopyButton";

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
  const finished = !!job && isTerminalJobStatus(job.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-b border-line pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-2">
          <Link href="/" className="inline-flex min-h-10 items-center gap-2 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Semua proyek
          </Link>
          <div>
            <h1 className="break-words text-2xl font-semibold text-ink">{job?.source_name && !job.source_name.startsWith("http") ? job.source_name : `Project ${jobId.slice(0, 8)}`}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-muted">
              {job && <span className={`rounded-full border px-2 py-0.5 text-xs ${JOB_STATUS_TONES[job.status]}`}>{JOB_STATUS_LABELS[job.status]}</span>}
              {campaignBrief && (
                <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-brand/15 px-2 py-0.5 text-xs font-medium text-brand-soft">
                  <ShieldCheck className="h-3 w-3 shrink-0" aria-hidden /><span className="truncate">{campaignBrief.name}</span>
                </span>
              )}
              {job && <span className="text-xs text-ink-subtle">Dibuat {formatDateTime(job.created_at)}</span>}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <CopyButton value={jobId} label="Copy ID" copiedLabel="Tersalin" />
          <button type="button" onClick={() => refetch()} className="cg-btn" title="Muat ulang job">
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} aria-hidden />
            Refresh
          </button>
          {canCancel && (
            <button
              type="button"
              onClick={() => cancelJob.mutate()}
              disabled={cancelJob.isPending}
              className="cg-btn border-rose-300 text-rose-600 hover:border-rose-400 hover:text-rose-600 dark:border-rose-400/40 dark:text-rose-200"
              title="Batalkan job"
            >
              {cancelJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              Batalkan
            </button>
          )}
        </div>
      </div>

      {isLoading && <JobPageSkeleton />}
      {error && (
        <div className="flex items-center gap-2 cg-alert">
          <AlertCircle className="h-4 w-4" />
          {error instanceof Error ? error.message : "Job tidak ditemukan"}
        </div>
      )}
      {cancelJob.error && (
        <div className="flex items-center gap-2 cg-alert">
          <OctagonX className="h-4 w-4" />
          {cancelJob.error instanceof Error ? cancelJob.error.message : "Gagal cancel job"}
        </div>
      )}
      {retryJob.error && (
        <div className="flex items-center gap-2 cg-alert">
          <OctagonX className="h-4 w-4" />
          {retryJob.error instanceof Error ? retryJob.error.message : "Gagal membuat job ulang"}
        </div>
      )}

      {/* While a job runs, progress is the page. Once it is done the editor leads
          and the pipeline detail collapses so the preview sits near the top. */}
      {job && !finished && (
        <>
          <JobProgressBar job={job} />
          <JobStageTimeline job={job} />
        </>
      )}
      {job && finished && (
        <details className="clipgen-panel rounded-panel">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-4 py-2.5 text-sm font-medium text-ink">
            <span>Detail pipeline &amp; progres</span>
            <span className="text-xs text-ink-subtle">{JOB_STATUS_LABELS[job.status]} · {job.progress}%</span>
          </summary>
          <div className="space-y-4 border-t border-line p-4">
            <JobProgressBar job={job} />
            <JobStageTimeline job={job} />
          </div>
        </details>
      )}

      {campaignBrief && (
        <section className="clipgen-panel rounded-panel p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand/15 text-brand-soft"><ShieldCheck className="h-4 w-4" aria-hidden /></div>
            <div className="min-w-0">
              <p className="cg-eyebrow">Campaign brief</p>
              <h2 className="mt-1 font-semibold text-ink">{campaignBrief.name}</h2>
              <p className="mt-1 text-sm text-ink-muted">{campaignBrief.min_clip_seconds}–{campaignBrief.max_clip_seconds} detik · hook {campaignBrief.hook_max_seconds} detik · {campaignBrief.hashtags.length} hashtag wajib</p>
            </div>
          </div>
          {campaignBrief.required_phrases.length > 0 && <p className="mt-3 border-t border-line pt-3 text-xs text-ink-muted">Narasi wajib: {campaignBrief.required_phrases.join(", ")}</p>}
        </section>
      )}

      {job && isActiveJobStatus(job.status) && (
        <div className="cg-alert-info px-4 py-3">
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
        <section className="clipgen-panel flex flex-col gap-3 rounded-panel p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink">Proses ulang</h2>
            <p className="mt-1 text-sm text-ink-muted">Buat job baru yang terhubung ke job ini tanpa mengubah hasil lama.</p>
          </div>
          <button
            type="button"
            onClick={() => retryJob.mutate()}
            disabled={retryJob.isPending}
            className="cg-btn-primary"
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
              <h2 className="cg-eyebrow">Klip</h2>
              <p className="mt-1 text-sm text-ink-muted">{readyClips.length} siap dari {clips?.length || 0} clip</p>
            </div>
            <a
              href={readyClips.length > 0 ? api.getJobArchiveUrl(jobId) : undefined}
              aria-disabled={readyClips.length === 0}
              className={`cg-btn w-fit ${readyClips.length === 0 ? "pointer-events-none cursor-not-allowed opacity-50" : ""}`}
              title="Download arsip semua clip"
            >
              <DownloadCloud className="h-4 w-4" />
              Download ZIP
            </a>
          </div>
          {clipsLoading && <ClipSkeleton />}
          {clipsError && (
            <div className="flex items-center gap-2 cg-alert">
              <AlertCircle className="h-4 w-4" />
              {clipsError instanceof Error ? clipsError.message : "Gagal memuat klip"}
            </div>
          )}
          {!clipsLoading && !clipsError && clips?.length === 0 && (
            <div className="clipgen-panel rounded-panel px-4 py-8 text-center text-sm text-ink-muted">
              Tidak ada klip
            </div>
          )}
          {readyClips.length > 0 && (
            <section className="rounded-panel border border-line bg-elevated/60 p-3 sm:p-4">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2 px-1">
                <div>
                  <p className="text-sm font-semibold text-ink">Pilih klip untuk diedit</p>
                  <p className="mt-1 text-xs text-ink-muted">Geser untuk melihat semua hasil. Detail, metadata, dan download tampil hanya untuk klip yang dipilih.</p>
                </div>
                <span className="rounded-full border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink-muted">{readyClips.length} klip</span>
              </div>
              <ClipGallery clips={readyClips} selectedClipId={selectedClip?.id || null} onSelect={setSelectedClipId} />
            </section>
          )}
          {selectedClip && (
            <section>
              <div className="mb-3 flex items-center justify-between gap-3"><div className="min-w-0"><p className="cg-eyebrow">Editor klip</p><h3 className="mt-1 truncate text-lg font-semibold text-ink">{selectedClip.title || "Klip terpilih"}</h3></div><span className="shrink-0 text-xs tabular-nums text-ink-subtle">{readyClips.findIndex((clip) => clip.id === selectedClip.id) + 1} / {readyClips.length}</span></div>
              <ClipEditor
                key={selectedClip.id}
                clip={selectedClip}
                clips={readyClips}
                sourceDurationSeconds={job.source_duration_seconds}
                campaignBrief={campaignBrief}
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
    <div className="clipgen-panel rounded-panel p-4">
      <div className="h-5 w-28 animate-pulse rounded bg-elevated" />
      <div className="mt-3 h-2 w-full animate-pulse rounded bg-elevated" />
    </div>
  );
}

function ClipSkeleton() {
  return (
    <div className="flex gap-3 overflow-hidden">
      {[0, 1, 2, 3].map((item) => (
        <div key={item} className="clipgen-panel w-32 shrink-0 overflow-hidden rounded-panel p-2">
          <div className="aspect-[9/16] animate-pulse rounded-xl bg-elevated" />
          <div className="mt-2 h-3 w-20 animate-pulse rounded bg-elevated" />
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
