"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Edit3, ExternalLink, Facebook, Loader2, Save, Scissors, Trash2, X, Youtube } from "lucide-react";
import { ClipResponse, parseHashtags } from "@/types/api";
import { api } from "@/lib/api";
import { useDeleteClip, useTrimClip, useUpdateClip } from "@/hooks/useClips";
import { formatDuration, formatPercent, formatSeconds } from "@/lib/status";
import { CopyButton } from "@/components/CopyButton";
import { ClipFeedback } from "@/components/ClipFeedback";

export function ClipCard({ clip }: { clip: ClipResponse }) {
  const [isEditing, setIsEditing] = useState(false);
  const [isTrimming, setIsTrimming] = useState(false);
  const [title, setTitle] = useState(clip.title || "");
  const [caption, setCaption] = useState(clip.caption || "");
  const [hashtagsInput, setHashtagsInput] = useState(
    parseHashtags(clip.hashtags).join(" ")
  );
  const [trimStart, setTrimStart] = useState(String(clip.start_time));
  const [trimEnd, setTrimEnd] = useState(String(clip.end_time));
  const [distributionPlatform, setDistributionPlatform] = useState<"youtube" | "facebook">("youtube");

  const hashtags = useMemo(() => parseHashtags(clip.hashtags), [clip.hashtags]);
  const hashtagsText = hashtags.map((tag) => `#${tag.replace(/^#+/, "")}`).join(" ");
  const captionBundle = [clip.caption, hashtagsText].filter(Boolean).join("\n\n");
  const distribution = clip.distribution;

  const updateClip = useUpdateClip(clip.job_id);
  const deleteClip = useDeleteClip(clip.job_id);
  const trimClip = useTrimClip(clip.job_id);

  useEffect(() => {
    setTitle(clip.title || "");
    setCaption(clip.caption || "");
    setHashtagsInput(parseHashtags(clip.hashtags).join(" "));
    setTrimStart(String(clip.start_time));
    setTrimEnd(String(clip.end_time));
  }, [clip.caption, clip.end_time, clip.hashtags, clip.start_time, clip.title]);

  if (clip.status === "failed") {
    return (
      <div className="border border-rose-200 bg-rose-50 p-4">
        <p className="text-sm font-medium text-rose-700">Clip gagal diproses</p>
        <p className="mt-1 text-sm text-rose-600">
          {formatSeconds(clip.start_time)} - {formatSeconds(clip.end_time)}
        </p>
      </div>
    );
  }

  const handleSave = () => {
    const hashtags = Array.from(
      new Set(
        hashtagsInput
          .split(/\s+/)
          .map((tag) => tag.trim().replace(/^#+/, ""))
          .filter(Boolean)
      )
    );

    updateClip.mutate({
      clipId: clip.id,
      data: {
        title,
        caption,
        hashtags,
      },
    }, {
      onSuccess: () => setIsEditing(false),
    });
  };

  const handleDelete = () => {
    if (!window.confirm("Hapus klip ini?")) return;
    deleteClip.mutate(clip.id);
  };

  const handleTrim = () => {
    const startTime = Number(trimStart);
    const endTime = Number(trimEnd);
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) return;
    trimClip.mutate({ clipId: clip.id, startTime, endTime }, { onSuccess: () => setIsTrimming(false) });
  };

  return (
    <article className="clipgen-panel p-4 shadow-sm">
      {clip.file_path ? (
        <div className="bg-black">
          <video
            src={api.getClipPreviewUrl(clip.id)}
            controls
            preload="metadata"
            className="max-h-[560px] min-h-56 w-full object-contain"
          />
        </div>
      ) : (
        <div className="flex min-h-56 w-full items-center justify-center bg-slate-100 text-sm text-slate-500 dark:bg-slate-900 dark:text-slate-400">
          Memproses
        </div>
      )}

      {isEditing ? (
        <div className="mt-4 space-y-3">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Judul"
            className="w-full border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-50 dark:focus:border-cyan-300"
          />
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Caption"
            className="h-24 w-full resize-none border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-50 dark:focus:border-cyan-300"
          />
          <input
            type="text"
            value={hashtagsInput}
            onChange={(e) => setHashtagsInput(e.target.value)}
            placeholder="hashtag1 hashtag2"
            className="w-full border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-50 dark:focus:border-cyan-300"
          />
          {updateClip.error && (
            <p className="border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {updateClip.error instanceof Error ? updateClip.error.message : "Gagal menyimpan"}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleSave}
              disabled={updateClip.isPending}
              className="inline-flex items-center gap-2 bg-slate-950 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
              title="Simpan metadata"
            >
              {updateClip.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Simpan
            </button>
            <button
              onClick={() => setIsEditing(false)}
              disabled={updateClip.isPending}
              className="inline-flex items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
              title="Batal"
            >
              <X className="h-4 w-4" />
              Batal
            </button>
          </div>
        </div>
      ) : isTrimming ? (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Mulai (detik)
              <input
                type="number"
                min="0"
                step="0.1"
                value={trimStart}
                onChange={(event) => setTrimStart(event.target.value)}
                className="mt-1 w-full border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Akhir (detik)
              <input
                type="number"
                min="0"
                step="0.1"
                value={trimEnd}
                onChange={(event) => setTrimEnd(event.target.value)}
                className="mt-1 w-full border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
          </div>
          {trimClip.error && <p className="border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{trimClip.error instanceof Error ? trimClip.error.message : "Trim gagal dibuat"}</p>}
          <div className="flex gap-2">
            <button onClick={handleTrim} disabled={trimClip.isPending} className="inline-flex items-center gap-2 bg-slate-950 px-3 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-cyan-300 dark:text-slate-950">
              {trimClip.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
              Render trim
            </button>
            <button onClick={() => setIsTrimming(false)} disabled={trimClip.isPending} className="inline-flex items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
              <X className="h-4 w-4" />
              Batal
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span>{formatSeconds(clip.start_time)} - {formatSeconds(clip.end_time)}</span>
              <span>{formatDuration(clip.start_time, clip.end_time)}</span>
              <span>Score {formatPercent(clip.highlight_score)}</span>
            </div>
            <h3 className="mt-1 text-base font-semibold text-slate-950 dark:text-slate-50">{clip.title || "(belum ada judul)"}</h3>
          </div>
          {clip.caption && <p className="text-sm leading-6 text-slate-700 dark:text-slate-300">{clip.caption}</p>}
          <div className="flex flex-wrap gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            {hashtags.map((tag) => (
              <span key={tag} className="border border-slate-200 bg-slate-50 px-2 py-0.5 dark:border-cyan-300/20 dark:bg-cyan-300/10 dark:text-cyan-100">
                #{tag.replace(/^#+/, "")}
              </span>
            ))}
          </div>

          {distribution && (
            <section className="border border-cyan-200 bg-cyan-50/70 p-3 dark:border-cyan-300/20 dark:bg-cyan-300/5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-cyan-800 dark:text-cyan-200">
                    Paket distribusi manual
                  </p>
                  <p className="mt-1 text-xs text-cyan-700 dark:text-cyan-100">
                    Video sudah ber-watermark <strong>@RidhoWahyu</strong>. Copy metadata ini ke upload form platform.
                  </p>
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => setDistributionPlatform("youtube")}
                    className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium ${distributionPlatform === "youtube" ? "bg-slate-950 text-white" : "border border-cyan-300 text-cyan-800 dark:text-cyan-100"}`}
                  >
                    <Youtube className="h-3.5 w-3.5" /> YouTube
                  </button>
                  <button
                    type="button"
                    onClick={() => setDistributionPlatform("facebook")}
                    className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium ${distributionPlatform === "facebook" ? "bg-slate-950 text-white" : "border border-cyan-300 text-cyan-800 dark:text-cyan-100"}`}
                  >
                    <Facebook className="h-3.5 w-3.5" /> Facebook
                  </button>
                </div>
              </div>
              {distributionPlatform === "youtube" ? (
                <div className="mt-3 space-y-2">
                  <DistributionField label="Title" value={distribution.youtube.title} />
                  <DistributionField label="Description" value={distribution.youtube.description} multiline />
                  <DistributionField label="Tags" value={distribution.youtube.tags.join(", ")} />
                  <p className="text-[11px] text-cyan-700 dark:text-cyan-200">
                    Hashtag: {distribution.youtube.hashtags || "(tidak ada)"}
                  </p>
                  <DistributionChecklist items={distribution.youtube.checklist} />
                </div>
              ) : (
                <div className="mt-3 space-y-2">
                  <DistributionField label="Caption Facebook" value={distribution.facebook.caption} multiline />
                  <p className="text-[11px] text-cyan-700 dark:text-cyan-200">
                    Hashtag: {distribution.facebook.hashtags || "(tidak ada)"}
                  </p>
                  <DistributionChecklist items={distribution.facebook.checklist} />
                </div>
              )}
              <p className="mt-2 text-[11px] text-cyan-700 dark:text-cyan-200">
                Referensi hashtag: {distribution.hashtag_source === "youtube_source_tags+clip_metadata" ? "metadata YouTube sumber + clip" : "fallback dari metadata clip"}.
              </p>
            </section>
          )}

          {deleteClip.error && (
            <p className="border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {deleteClip.error instanceof Error ? deleteClip.error.message : "Gagal menghapus"}
            </p>
          )}
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              onClick={() => setIsEditing(true)}
              className="inline-flex items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-cyan-300"
              title="Edit metadata"
            >
              <Edit3 className="h-4 w-4" />
              Edit
            </button>
            <button
              onClick={() => setIsTrimming(true)}
              className="inline-flex items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-cyan-300"
              title="Atur ulang rentang klip"
            >
              <Scissors className="h-4 w-4" />
              Trim
            </button>
            <CopyButton value={captionBundle} label="Copy caption" copiedLabel="Copied" />
            {clip.file_path && (
              <>
                <a
                  href={api.getClipPreviewUrl(clip.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:border-cyan-300"
                  title="Open preview"
                >
                  <ExternalLink className="h-4 w-4" />
                  Preview
                </a>
                <a
                  href={api.getClipDownloadUrl(clip.id)}
                  download
                  className="inline-flex items-center gap-2 bg-slate-950 px-3 py-2 text-sm font-medium text-white"
                  title="Download clip"
                >
                  <Download className="h-4 w-4" />
                  Download
                </a>
              </>
            )}
            <button
              onClick={handleDelete}
              disabled={deleteClip.isPending}
              className="inline-flex items-center gap-2 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 hover:border-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
              title="Hapus clip"
            >
              {deleteClip.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Hapus
            </button>
            <ClipFeedback clipId={clip.id} />
          </div>
        </div>
      )}
    </article>
  );
}

function DistributionField({ label, value, multiline = false }: { label: string; value: string; multiline?: boolean }) {
  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-cyan-800 dark:text-cyan-200">{label}</p>
        {multiline ? (
          <textarea readOnly value={value} className="min-h-16 w-full resize-y border border-cyan-200 bg-white px-2 py-1.5 text-xs leading-5 text-slate-700 dark:border-cyan-300/20 dark:bg-slate-950 dark:text-slate-200" />
        ) : (
          <input readOnly value={value} className="w-full border border-cyan-200 bg-white px-2 py-1.5 text-xs text-slate-700 dark:border-cyan-300/20 dark:bg-slate-950 dark:text-slate-200" />
        )}
      </div>
      <CopyButton value={value} label="Copy" copiedLabel="Copied" />
    </div>
  );
}

function DistributionChecklist({ items }: { items: string[] }) {
  return (
    <div className="border-t border-cyan-200 pt-2 text-[11px] text-cyan-800 dark:border-cyan-300/20 dark:text-cyan-100">
      <p className="font-semibold">Checklist upload manual</p>
      <ol className="mt-1 list-inside list-decimal space-y-0.5">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ol>
    </div>
  );
}
