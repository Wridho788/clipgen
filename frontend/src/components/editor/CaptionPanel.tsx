"use client";

import { Plus, Trash2 } from "lucide-react";

import { cueOutsideTrim, formatClock, newCueId, parseClock } from "@/lib/editGeometry";
import { CaptionCue, CaptionStyle, ClipEdit } from "@/types/api";

type CaptionPanelProps = {
  edit: ClipEdit;
  playheadMs: number;
  onChange: (producer: (edit: ClipEdit) => ClipEdit, options?: { history?: boolean }) => void;
  onSeek: (ms: number) => void;
};

const COLORS = ["#FFFFFF", "#FFE14D", "#22D3EE", "#000000"];

export function CaptionPanel({ edit, playheadMs, onChange, onSeek }: CaptionPanelProps) {
  const captions = edit.captions;
  const style = captions.style;
  const cues = [...captions.cues].sort((a, b) => a.start_ms - b.start_ms);
  const corrected = cues.filter((cue) => cue.original_text != null && cue.text !== cue.original_text).length;
  const hiddenCount = cues.filter((cue) => cueOutsideTrim(cue, edit)).length;

  const setStyle = (patch: Partial<CaptionStyle>) =>
    onChange((current) => ({ ...current, captions: { ...current.captions, style: { ...current.captions.style, ...patch } } }));
  const setCue = (id: string, patch: Partial<CaptionCue>, history = true) =>
    onChange(
      (current) => ({
        ...current,
        captions: {
          ...current.captions,
          cues: current.captions.cues.map((cue) => (cue.id === id ? { ...cue, ...patch } : cue)),
        },
      }),
      { history },
    );
  const removeCue = (id: string) =>
    onChange((current) => ({
      ...current,
      captions: { ...current.captions, cues: current.captions.cues.filter((cue) => cue.id !== id) },
    }));
  const addCue = () => {
    const start = Math.max(edit.trim_start_ms, Math.min(Math.round(playheadMs), edit.trim_end_ms - 500));
    const cue: CaptionCue = { id: newCueId(), start_ms: start, end_ms: Math.min(edit.trim_end_ms, start + 2000), text: "Caption baru", original_text: null };
    onChange((current) => ({ ...current, captions: { ...current.captions, enabled: true, cues: [...current.captions.cues, cue] } }));
  };

  return (
    <div className="space-y-4">
      <label className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800">
        <span>
          <span className="block text-sm font-medium text-slate-900 dark:text-slate-100">Burn caption ke video</span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">
            {cues.length} baris · {corrected} dikoreksi{hiddenCount ? ` · ${hiddenCount} di luar trim (disimpan, tidak dirender)` : ""}
          </span>
        </span>
        <input
          type="checkbox"
          role="switch"
          aria-label="Burn caption ke video"
          checked={captions.enabled}
          onChange={(event) => onChange((current) => ({ ...current, captions: { ...current.captions, enabled: event.target.checked } }))}
          className="h-5 w-5 accent-violet-600"
        />
      </label>

      <fieldset className="grid gap-3 sm:grid-cols-2" disabled={!captions.enabled}>
        <legend className="sr-only">Gaya caption</legend>
        <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
          Ukuran font ({style.font_size})
          <input type="range" min={24} max={140} value={style.font_size} onChange={(event) => setStyle({ font_size: Number(event.target.value) })} className="mt-2 w-full accent-violet-600" />
        </label>
        <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
          Posisi vertikal ({Math.round(style.position_y * 100)}% dari atas)
          <input type="range" min={8} max={92} value={Math.round(style.position_y * 100)} onChange={(event) => setStyle({ position_y: Number(event.target.value) / 100 })} className="mt-2 w-full accent-violet-600" />
        </label>
        <div className="text-xs font-medium text-slate-600 dark:text-slate-300">
          Warna teks
          <div className="mt-1.5 flex items-center gap-1.5">
            {COLORS.map((color) => (
              <button
                key={color}
                type="button"
                onClick={() => setStyle({ text_color: color })}
                aria-label={`Warna teks ${color}`}
                aria-pressed={style.text_color === color}
                className={`h-7 w-7 rounded-full border-2 ${style.text_color === color ? "border-violet-500 ring-2 ring-violet-300" : "border-line-strong"}`}
                style={{ backgroundColor: color }}
              />
            ))}
            <input type="color" aria-label="Warna teks kustom" value={style.text_color} onChange={(event) => setStyle({ text_color: event.target.value.toUpperCase() })} className="h-7 w-9 cursor-pointer rounded border border-line-strong" />
          </div>
        </div>
        <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
          Latar
          <select value={style.background} onChange={(event) => setStyle({ background: event.target.value as CaptionStyle["background"] })} className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950">
            <option value="outline">Outline</option>
            <option value="box">Kotak</option>
            <option value="none">Tanpa latar</option>
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
          Maks karakter per baris ({style.max_chars_per_line})
          <input type="range" min={12} max={48} value={style.max_chars_per_line} onChange={(event) => setStyle({ max_chars_per_line: Number(event.target.value) })} className="mt-2 w-full accent-violet-600" />
        </label>
        <label className="flex items-center gap-2 self-end text-xs font-medium text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={style.bold} onChange={(event) => setStyle({ bold: event.target.checked })} className="accent-violet-600" />
          Tebal
        </label>
      </fieldset>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Teks & timing</p>
          <button type="button" onClick={addCue} className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:text-slate-200">
            <Plus className="h-3.5 w-3.5" /> Tambah di playhead
          </button>
        </div>
        {cues.length === 0 && <p className="text-sm text-ink-subtle">Belum ada caption. Transkrip tidak tersedia untuk klip ini; tambahkan baris secara manual.</p>}
        <ol className="max-h-80 space-y-1.5 overflow-y-auto pr-1" aria-label="Daftar caption">
          {cues.map((cue, index) => {
            const outside = cueOutsideTrim(cue, edit);
            const active = playheadMs >= cue.start_ms && playheadMs < cue.end_ms;
            return (
              <li key={cue.id} className={`rounded-lg border p-2 ${active ? "border-violet-400 bg-violet-50/60 dark:bg-violet-400/10" : "border-slate-200 dark:border-slate-800"} ${outside ? "opacity-60" : ""}`}>
                <div className="flex items-center gap-1.5 text-[11px] text-ink-subtle">
                  <button type="button" onClick={() => onSeek(Math.min(Math.max(cue.start_ms, edit.trim_start_ms), edit.trim_end_ms - 1))} className="font-mono underline-offset-2 hover:underline" aria-label={`Putar caption ${index + 1}`}>
                    #{index + 1}
                  </button>
                  <CueTime label="mulai" valueMs={cue.start_ms} onCommit={(value) => value < cue.end_ms && setCue(cue.id, { start_ms: value })} />
                  <span>→</span>
                  <CueTime label="akhir" valueMs={cue.end_ms} onCommit={(value) => value > cue.start_ms && setCue(cue.id, { end_ms: value })} />
                  {outside && <span className="rounded bg-amber-100 px-1 text-amber-800">di luar trim</span>}
                  {cue.original_text != null && cue.text !== cue.original_text && <span className="rounded bg-emerald-100 px-1 text-emerald-800">dikoreksi</span>}
                  <button type="button" onClick={() => removeCue(cue.id)} className="ml-auto text-slate-400 hover:text-rose-600" aria-label={`Hapus caption ${index + 1}`}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                <textarea
                  value={cue.text}
                  aria-label={`Teks caption ${index + 1}`}
                  onChange={(event) => setCue(cue.id, { text: event.target.value }, false)}
                  onBlur={(event) => setCue(cue.id, { text: event.target.value.replace(/\s+/g, " ").trim() })}
                  rows={1}
                  maxLength={300}
                  className="mt-1 w-full resize-y rounded border border-slate-200 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950"
                />
              </li>
            );
          })}
        </ol>
        <p className="text-[11px] text-ink-subtle dark:text-slate-400">
          Kebijakan trim: caption yang seluruhnya di luar trim tetap disimpan tetapi tidak dirender; caption yang terpotong batas trim dipendekkan saat render. Membuat ulang metadata tidak mengubah caption yang sudah dikoreksi.
        </p>
      </div>
    </div>
  );
}

function CueTime({ label, valueMs, onCommit }: { label: string; valueMs: number; onCommit: (ms: number) => void }) {
  return (
    <input
      key={valueMs}
      defaultValue={formatClock(valueMs)}
      aria-label={`Waktu ${label}`}
      onBlur={(event) => {
        const parsed = parseClock(event.target.value);
        if (parsed !== null && parsed !== valueMs) onCommit(parsed);
        else event.target.value = formatClock(valueMs);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") (event.target as HTMLInputElement).blur();
      }}
      className="w-16 rounded border border-transparent bg-transparent px-1 font-mono hover:border-line-strong focus:border-brand focus:outline-none"
    />
  );
}
