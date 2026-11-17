"use client";

import { useEffect, useState } from "react";
import { ArrowLeftToLine, ArrowRightToLine, RotateCcw } from "lucide-react";

import { formatClock, MAX_CLIP_MS, MIN_CLIP_MS, parseClock, validateTrim } from "@/lib/editGeometry";
import { ClipEdit } from "@/types/api";

type TrimPanelProps = {
  edit: ClipEdit;
  playheadMs: number;
  sourceDurationMs: number | null;
  suggested: { startMs: number; endMs: number } | null;
  onChange: (startMs: number, endMs: number) => void;
};

export function TrimPanel({ edit, playheadMs, sourceDurationMs, suggested, onChange }: TrimPanelProps) {
  const error = validateTrim(edit, sourceDurationMs);
  const duration = edit.trim_end_ms - edit.trim_start_ms;
  const isSuggested = suggested && suggested.startMs === edit.trim_start_ms && suggested.endMs === edit.trim_end_ms;

  const clampStart = (value: number) => Math.max(0, Math.min(value, edit.trim_end_ms - MIN_CLIP_MS));
  const clampEnd = (value: number) => {
    const limit = sourceDurationMs || Number.MAX_SAFE_INTEGER;
    return Math.min(limit, Math.max(value, edit.trim_start_ms + MIN_CLIP_MS), edit.trim_start_ms + MAX_CLIP_MS);
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <BoundaryField
          label="Mulai"
          valueMs={edit.trim_start_ms}
          onCommit={(value) => onChange(clampStart(value), edit.trim_end_ms)}
          onNudge={(delta) => onChange(clampStart(edit.trim_start_ms + delta), edit.trim_end_ms)}
          setLabel="Set mulai di playhead"
          onSetFromPlayhead={() => onChange(clampStart(Math.round(playheadMs)), edit.trim_end_ms)}
          icon={<ArrowLeftToLine className="h-3.5 w-3.5" />}
          shortcut="I"
        />
        <BoundaryField
          label="Akhir"
          valueMs={edit.trim_end_ms}
          onCommit={(value) => onChange(edit.trim_start_ms, clampEnd(value))}
          onNudge={(delta) => onChange(edit.trim_start_ms, clampEnd(edit.trim_end_ms + delta))}
          setLabel="Set akhir di playhead"
          onSetFromPlayhead={() => onChange(edit.trim_start_ms, clampEnd(Math.round(playheadMs)))}
          icon={<ArrowRightToLine className="h-3.5 w-3.5" />}
          shortcut="O"
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900">
        <span data-testid="trim-duration">
          Durasi <strong>{(duration / 1000).toFixed(1)} detik</strong>
          <span className="ml-2 text-xs text-ink-subtle">playhead {formatClock(playheadMs)}</span>
        </span>
        {suggested && (
          <button
            type="button"
            onClick={() => onChange(suggested.startMs, suggested.endMs)}
            disabled={!!isSuggested}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset ke saran AI ({formatClock(suggested.startMs)}–{formatClock(suggested.endMs)})
          </button>
        )}
      </div>
      {error && <p role="alert" className="cg-alert">{error}</p>}
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Seek dan play tidak mengubah batas klip. Video sumber tidak pernah diubah; trim disimpan sebagai data edit dalam milidetik.
      </p>
    </div>
  );
}

function BoundaryField({
  label,
  valueMs,
  onCommit,
  onNudge,
  onSetFromPlayhead,
  setLabel,
  icon,
  shortcut,
}: {
  label: string;
  valueMs: number;
  onCommit: (valueMs: number) => void;
  onNudge: (deltaMs: number) => void;
  onSetFromPlayhead: () => void;
  setLabel: string;
  icon: React.ReactNode;
  shortcut: string;
}) {
  const [text, setText] = useState(formatClock(valueMs));
  const [invalid, setInvalid] = useState(false);
  useEffect(() => {
    setText(formatClock(valueMs));
    setInvalid(false);
  }, [valueMs]);

  const commit = () => {
    const parsed = parseClock(text);
    if (parsed === null) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    if (parsed !== valueMs) onCommit(parsed);
  };

  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
        {label} (m:ss.d)
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
          }}
          aria-invalid={invalid}
          className={`mt-1 w-full rounded-md border bg-white px-3 py-2 font-mono text-sm outline-none focus:border-cyan-500 dark:bg-slate-950 ${invalid ? "border-rose-400" : "border-slate-300 dark:border-slate-700"}`}
        />
      </label>
      <div className="flex flex-wrap gap-1">
        {[-1000, -100, 100, 1000].map((delta) => (
          <button
            key={delta}
            type="button"
            onClick={() => onNudge(delta)}
            aria-label={`${label} ${delta > 0 ? "maju" : "mundur"} ${Math.abs(delta) / 1000} detik`}
            className="rounded border border-slate-300 px-1.5 py-0.5 font-mono text-[11px] text-slate-600 hover:border-slate-500 dark:border-slate-700 dark:text-slate-300"
          >
            {delta > 0 ? "+" : "−"}{Math.abs(delta) / 1000}s
          </button>
        ))}
        <button
          type="button"
          onClick={onSetFromPlayhead}
          title={`${setLabel} (${shortcut})`}
          className="inline-flex items-center gap-1 rounded border border-cyan-300 bg-cyan-50 px-2 py-0.5 text-[11px] font-medium text-cyan-800 dark:border-cyan-400/40 dark:bg-cyan-400/10 dark:text-cyan-100"
        >
          {icon}
          {setLabel}
          <kbd className="ml-0.5 rounded bg-white/70 px-1 font-mono text-[10px] dark:bg-slate-900">{shortcut}</kbd>
        </button>
      </div>
    </div>
  );
}
