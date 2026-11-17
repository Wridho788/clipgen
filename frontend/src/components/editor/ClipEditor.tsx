"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, CloudOff, Loader2, Pause, Play, Redo2, Undo2 } from "lucide-react";

import { api } from "@/lib/api";
import { formatClock, validateTrim } from "@/lib/editGeometry";
import { useClipEditor } from "@/hooks/useClipEditor";
import { ClipCard } from "@/components/ClipCard";
import { CandidateReview } from "@/components/editor/CandidateReview";
import { CaptionPanel } from "@/components/editor/CaptionPanel";
import { EditorPreview } from "@/components/editor/EditorPreview";
import { ExportPanel } from "@/components/editor/ExportPanel";
import { FormatPanel } from "@/components/editor/FormatPanel";
import { TrimPanel } from "@/components/editor/TrimPanel";
import { CampaignPanel } from "@/components/editor/CampaignPanel";
import { CampaignBrief, ClipResponse, RejectionReason } from "@/types/api";

type Tab = "trim" | "captions" | "format" | "metadata" | "campaign";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "trim", label: "Trim" },
  { id: "captions", label: "Caption" },
  { id: "format", label: "Format & framing" },
  { id: "metadata", label: "Metadata & distribusi" },
  { id: "campaign", label: "Campaign" },
];

type ClipEditorProps = {
  clip: ClipResponse;
  clips: ClipResponse[];
  sourceDurationSeconds: number | null;
  /** Campaign rules pinned to this job; null when the job runs without one. */
  campaignBrief?: CampaignBrief | null;
  onSelect: (clipId: string) => void;
};

/** Mount with ``key={clip.id}`` so each clip gets its own draft and autosave. */
export function ClipEditor({ clip, clips, sourceDurationSeconds, campaignBrief = null, onSelect }: ClipEditorProps) {
  const queryClient = useQueryClient();
  const editor = useClipEditor(clip);
  const draft = editor.draft;
  const videoRef = useRef<HTMLVideoElement>(null);
  const [tab, setTab] = useState<Tab>("trim");
  const [playheadMs, setPlayheadMs] = useState(draft?.trim_start_ms ?? 0);
  const [playing, setPlaying] = useState(false);
  const [sourceSize, setSourceSize] = useState<{ width: number; height: number } | null>(null);
  const sourceDurationMs = sourceDurationSeconds ? Math.round(sourceDurationSeconds * 1000) : null;
  const trimRef = useRef({ start: draft?.trim_start_ms ?? 0, end: draft?.trim_end_ms ?? 0 });
  trimRef.current = { start: draft?.trim_start_ms ?? 0, end: draft?.trim_end_ms ?? 0 };

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["clips", clip.job_id] });
  const writeClip = (updated: ClipResponse) =>
    queryClient.setQueryData<ClipResponse[]>(["clips", clip.job_id], (current) =>
      current?.map((item) => (item.id === updated.id ? updated : item)),
    );

  const render = useMutation({
    mutationFn: async () => {
      const saved = await editor.save();
      if (!saved) throw new Error("Edit belum tersimpan; render dibatalkan agar file sesuai edit yang tersimpan.");
      return api.renderClip(clip.id);
    },
    onSuccess: writeClip,
  });
  const review = useMutation({
    mutationFn: ({ status, reason }: { status: "suggested" | "accepted" | "rejected"; reason?: RejectionReason }) =>
      api.reviewClip(clip.id, status, reason),
    onSuccess: writeClip,
  });
  const duplicate = useMutation({
    mutationFn: async () => {
      await editor.save();
      return api.duplicateClip(clip.id);
    },
    onSuccess: async (copy) => {
      await invalidate();
      onSelect(copy.id);
    },
  });
  const reorder = useMutation({
    mutationFn: (ids: string[]) => api.reorderClips(clip.job_id, ids),
    onSuccess: (ordered) => queryClient.setQueryData(["clips", clip.job_id], ordered),
  });

  // Playhead tracking: rAF while playing (caption timing), events otherwise.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let frame = 0;
    const tick = () => {
      const ms = video.currentTime * 1000;
      setPlayheadMs(ms);
      if (!video.paused && ms >= trimRef.current.end) {
        video.pause();
        video.currentTime = trimRef.current.start / 1000;
      }
      if (!video.paused) frame = requestAnimationFrame(tick);
    };
    const onPlay = () => {
      setPlaying(true);
      const ms = video.currentTime * 1000;
      if (ms < trimRef.current.start - 50 || ms >= trimRef.current.end - 50) video.currentTime = trimRef.current.start / 1000;
      frame = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      cancelAnimationFrame(frame);
      setPlayheadMs(video.currentTime * 1000);
    };
    const onSeeked = () => setPlayheadMs(video.currentTime * 1000);
    const onLoaded = () => {
      video.currentTime = trimRef.current.start / 1000;
    };
    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("seeked", onSeeked);
    video.addEventListener("loadedmetadata", onLoaded);
    return () => {
      cancelAnimationFrame(frame);
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("seeked", onSeeked);
      video.removeEventListener("loadedmetadata", onLoaded);
    };
  }, []);

  const seek = useCallback((ms: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, ms) / 1000;
    setPlayheadMs(ms);
  }, []);

  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) void video.play().catch(() => undefined);
    else video.pause();
  }, []);

  const setTrim = useCallback(
    (startMs: number, endMs: number) => {
      editor.update((current) =>
        current.trim_start_ms === startMs && current.trim_end_ms === endMs
          ? current
          : { ...current, trim_start_ms: startMs, trim_end_ms: endMs },
      );
    },
    [editor],
  );

  // Keyboard shortcuts (ignored while typing in a field).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable);
      const mod = event.ctrlKey || event.metaKey;
      if (mod && event.key.toLowerCase() === "z") {
        if (typing) return;
        event.preventDefault();
        if (event.shiftKey) editor.redo();
        else editor.undo();
        return;
      }
      if (mod && event.key.toLowerCase() === "y") {
        if (typing) return;
        event.preventDefault();
        editor.redo();
        return;
      }
      if (typing || mod || event.altKey || !draft) return;
      const video = videoRef.current;
      const now = Math.round((video?.currentTime || 0) * 1000);
      if (event.key === " ") {
        event.preventDefault();
        togglePlay();
      } else if (event.key.toLowerCase() === "i") {
        if (now < draft.trim_end_ms) setTrim(now, draft.trim_end_ms);
      } else if (event.key.toLowerCase() === "o") {
        if (now > draft.trim_start_ms) setTrim(draft.trim_start_ms, now);
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const step = event.shiftKey ? 100 : 1000;
        seek(now + (event.key === "ArrowLeft" ? -step : step));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [draft, editor, seek, setTrim, togglePlay]);

  if (!draft) {
    return <ClipCard clip={clip} />;
  }

  const trimError = validateTrim(draft, sourceDurationMs);
  const index = clips.findIndex((item) => item.id === clip.id);
  const move = (direction: -1 | 1) => {
    const ids = clips.map((item) => item.id);
    const target = index + direction;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorder.mutate(ids);
  };
  const suggested =
    clip.suggested_start_time != null && clip.suggested_end_time != null
      ? { startMs: Math.round(clip.suggested_start_time * 1000), endMs: Math.round(clip.suggested_end_time * 1000) }
      : null;
  const trimSpan = Math.max(1, draft.trim_end_ms - draft.trim_start_ms);
  const progress = Math.min(1, Math.max(0, (playheadMs - draft.trim_start_ms) / trimSpan));

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="space-y-3">
        <EditorPreview
          edit={draft}
          sourceUrl={api.getClipSourceUrl(clip.id)}
          fallbackUrl={clip.file_path ? api.getClipPreviewUrl(clip.id, clip.rendered_revision) : null}
          videoRef={videoRef}
          playheadMs={playheadMs}
          sourceSize={sourceSize}
          onSourceSize={(width, height) => setSourceSize({ width, height })}
        />
        <div className="flex items-center gap-3">
          <button type="button" onClick={togglePlay} aria-label={playing ? "Jeda" : "Putar klip"} className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-strong text-white">
            {playing ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
          </button>
          <input
            type="range"
            aria-label="Posisi di dalam klip"
            min={draft.trim_start_ms}
            max={draft.trim_end_ms}
            step={50}
            value={Math.min(draft.trim_end_ms, Math.max(draft.trim_start_ms, Math.round(playheadMs)))}
            onChange={(event) => seek(Number(event.target.value))}
            className="flex-1 accent-violet-600"
            style={{ backgroundSize: `${progress * 100}% 100%` }}
          />
          <span className="w-28 text-right font-mono text-xs text-ink-subtle">
            {formatClock(Math.max(0, playheadMs - draft.trim_start_ms))} / {formatClock(trimSpan)}
          </span>
        </div>
        <p className="text-[11px] text-ink-subtle dark:text-slate-400">
          Shortcut: <kbd>Spasi</kbd> putar/jeda · <kbd>I</kbd>/<kbd>O</kbd> set mulai/akhir · <kbd>←</kbd>/<kbd>→</kbd> geser 1 dtk (Shift: 0,1 dtk) · <kbd>Ctrl+Z</kbd> undo · <kbd>Ctrl+Shift+Z</kbd> redo
        </p>
        <CandidateReview
          clip={clip}
          position={index + 1}
          total={clips.length}
          busy={review.isPending || duplicate.isPending || reorder.isPending}
          onReview={(status, reason) => review.mutate({ status, reason })}
          onDuplicate={() => duplicate.mutate()}
          onMove={move}
        />
        {(review.error || duplicate.error || reorder.error) && (
          <p role="alert" className="cg-alert">
            {[review.error, duplicate.error, reorder.error].find(Boolean)?.message}
          </p>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div role="tablist" aria-label="Panel editor" className="flex flex-wrap gap-1 rounded-lg border border-line bg-elevated p-1">
            {TABS.filter((item) => item.id !== "campaign" || campaignBrief).map((item) => (
              <button
                key={item.id}
                role="tab"
                type="button"
                aria-selected={tab === item.id}
                onClick={() => setTab(item.id)}
                className={`min-h-9 rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${tab === item.id ? "bg-brand/20 font-semibold text-brand-soft" : "text-ink-muted hover:text-ink"}`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={editor.undo} disabled={!editor.canUndo} aria-label="Undo" title="Undo (Ctrl+Z)" className="rounded-md border border-slate-300 p-1.5 disabled:opacity-40 dark:border-slate-700">
              <Undo2 className="h-4 w-4" />
            </button>
            <button type="button" onClick={editor.redo} disabled={!editor.canRedo} aria-label="Redo" title="Redo (Ctrl+Shift+Z)" className="rounded-md border border-slate-300 p-1.5 disabled:opacity-40 dark:border-slate-700">
              <Redo2 className="h-4 w-4" />
            </button>
            <SaveIndicator state={editor.saveState} />
          </div>
        </div>

        {editor.saveError && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-2 cg-alert-warn">
            <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{editor.saveError}</span>
            {editor.saveState === "conflict" ? (
              <button type="button" onClick={() => void editor.reloadFromServer()} className="rounded-md bg-amber-600 px-2.5 py-1 text-xs font-semibold text-white">Muat versi terbaru</button>
            ) : (
              <button type="button" onClick={() => void editor.save()} className="rounded-md bg-amber-600 px-2.5 py-1 text-xs font-semibold text-white">Coba simpan lagi</button>
            )}
          </div>
        )}

        <div role="tabpanel" className="rounded-xl border border-line p-3">
          {tab === "trim" && (
            <TrimPanel edit={draft} playheadMs={playheadMs} sourceDurationMs={sourceDurationMs} suggested={suggested} onChange={setTrim} />
          )}
          {tab === "captions" && <CaptionPanel edit={draft} playheadMs={playheadMs} onChange={editor.update} onSeek={seek} />}
          {tab === "format" && <FormatPanel edit={draft} onChange={editor.update} />}
          {tab === "metadata" && <ClipCard clip={clip} embedded />}
          {tab === "campaign" && campaignBrief && (
            <CampaignPanel brief={campaignBrief} compliance={clip.distribution?.compliance ?? null} draft={draft} />
          )}
        </div>

        <ExportPanel
          clip={clip}
          hasUnsavedChanges={editor.saveState !== "saved"}
          invalidReason={trimError}
          isSubmitting={render.isPending}
          submitError={render.error instanceof Error ? render.error.message : null}
          onRender={() => render.mutate()}
        />
      </div>
    </div>
  );
}

function SaveIndicator({ state }: { state: ReturnType<typeof useClipEditor>["saveState"] }) {
  const map = {
    saved: { icon: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />, label: "Tersimpan" },
    dirty: { icon: <span className="h-2 w-2 rounded-full bg-amber-500" />, label: "Perubahan belum tersimpan" },
    saving: { icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />, label: "Menyimpan…" },
    error: { icon: <CloudOff className="h-3.5 w-3.5 text-rose-600" />, label: "Gagal menyimpan" },
    conflict: { icon: <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />, label: "Konflik versi" },
  }[state];
  return (
    <span role="status" aria-live="polite" data-testid="save-status" className="inline-flex items-center gap-1.5 rounded-md border border-line bg-elevated px-2 py-1 text-xs text-ink-muted">
      {map.icon}
      {map.label}
    </span>
  );
}
