"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Edit3, ExternalLink, Loader2, Save, Trash2, X } from "lucide-react";
import { ClipResponse, parseHashtags } from "@/types/api";
import { api } from "@/lib/api";
import { useDeleteClip, useUpdateClip } from "@/hooks/useClips";
import { formatDuration, formatPercent, formatSeconds } from "@/lib/status";
import { CopyButton } from "@/components/CopyButton";

export function ClipCard({ clip }: { clip: ClipResponse }) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(clip.title || "");
  const [caption, setCaption] = useState(clip.caption || "");
  const [hashtagsInput, setHashtagsInput] = useState(
    parseHashtags(clip.hashtags).join(" ")
  );

  const hashtags = useMemo(() => parseHashtags(clip.hashtags), [clip.hashtags]);
  const hashtagsText = hashtags.map((tag) => `#${tag.replace(/^#+/, "")}`).join(" ");
  const captionBundle = [clip.caption, hashtagsText].filter(Boolean).join("\n\n");

  const updateClip = useUpdateClip(clip.job_id);
  const deleteClip = useDeleteClip(clip.job_id);

  useEffect(() => {
    setTitle(clip.title || "");
    setCaption(clip.caption || "");
    setHashtagsInput(parseHashtags(clip.hashtags).join(" "));
  }, [clip.caption, clip.hashtags, clip.title]);

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
          </div>
        </div>
      )}
    </article>
  );
}
