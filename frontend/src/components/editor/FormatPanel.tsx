"use client";

import { PRESET_LABELS } from "@/lib/editGeometry";
import { ClipEdit, OutputPreset, VisualStyle } from "@/types/api";

type FormatPanelProps = {
  edit: ClipEdit;
  onChange: (producer: (edit: ClipEdit) => ClipEdit, options?: { history?: boolean }) => void;
};

const STYLE_LABELS: Record<Exclude<VisualStyle, "clean">, string> = {
  crop: "Crop (isi kanvas)",
  zoom: "Zoom 1.12×",
  blur: "Latar blur",
  split: "Split atas/bawah",
};

export function FormatPanel({ edit, onChange }: FormatPanelProps) {
  const isOriginal = edit.output_preset === "original";
  const usesFocus = !isOriginal && (edit.visual_style === "crop" || edit.visual_style === "zoom" || edit.visual_style === "split");

  const setPreset = (preset: OutputPreset) =>
    onChange((current) => ({
      ...current,
      output_preset: preset,
      // Mirror backend normalisation: original keeps the source frame clean;
      // a social canvas needs a fill style.
      visual_style: preset === "original" ? "clean" : current.visual_style === "clean" ? "crop" : current.visual_style,
    }));

  return (
    <div className="space-y-4">
      <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
        Format output
        <select
          value={edit.output_preset}
          onChange={(event) => setPreset(event.target.value as OutputPreset)}
          className="mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
        >
          {(Object.keys(PRESET_LABELS) as OutputPreset[]).map((preset) => (
            <option key={preset} value={preset}>{PRESET_LABELS[preset]}</option>
          ))}
        </select>
      </label>

      {!isOriginal && (
        <fieldset>
          <legend className="text-xs font-medium text-slate-600 dark:text-slate-300">Cara mengisi kanvas</legend>
          <div className="mt-1.5 grid grid-cols-2 gap-1.5">
            {(Object.keys(STYLE_LABELS) as Array<keyof typeof STYLE_LABELS>).map((style) => (
              <button
                key={style}
                type="button"
                aria-pressed={edit.visual_style === style}
                onClick={() => onChange((current) => ({ ...current, visual_style: style }))}
                className={`rounded-md border px-2 py-1.5 text-xs ${edit.visual_style === style ? "border-violet-500 bg-violet-50 font-semibold text-violet-800 dark:bg-violet-400/10 dark:text-violet-100" : "border-slate-300 text-slate-700 dark:border-slate-700 dark:text-slate-200"}`}
              >
                {STYLE_LABELS[style]}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {usesFocus ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
            Posisi horizontal ({Math.round(edit.framing.focus_x * 100)}%)
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(edit.framing.focus_x * 100)}
              onChange={(event) => onChange((current) => ({ ...current, framing: { ...current.framing, focus_x: Number(event.target.value) / 100 } }))}
              className="mt-2 w-full accent-violet-600"
            />
          </label>
          <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
            Posisi vertikal ({Math.round(edit.framing.focus_y * 100)}%)
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(edit.framing.focus_y * 100)}
              onChange={(event) => onChange((current) => ({ ...current, framing: { ...current.framing, focus_y: Number(event.target.value) / 100 } }))}
              className="mt-2 w-full accent-violet-600"
            />
          </label>
          <p className="text-[11px] text-ink-subtle sm:col-span-2">0% = tepi kiri/atas, 50% = tengah. Tidak ada tepi kosong: kanvas selalu terisi penuh. Tracking wajah otomatis belum tersedia.</p>
        </div>
      ) : (
        !isOriginal && <p className="text-xs text-ink-subtle">Latar blur menampilkan seluruh frame sumber; posisi crop tidak berlaku.</p>
      )}

      <div className="space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
        <Toggle label="Sertakan audio" checked={edit.audio.enabled} onChange={(value) => onChange((current) => ({ ...current, audio: { ...current.audio, enabled: value } }))} />
        <Toggle
          label="Normalisasi loudness (-16 LUFS)"
          checked={edit.audio.normalize}
          disabled={!edit.audio.enabled}
          onChange={(value) => onChange((current) => ({ ...current, audio: { ...current.audio, normalize: value } }))}
        />
        <Toggle label="Watermark kreator" checked={edit.watermark_enabled} onChange={(value) => onChange((current) => ({ ...current, watermark_enabled: value }))} />
      </div>
    </div>
  );
}

function Toggle({ label, checked, disabled, onChange }: { label: string; checked: boolean; disabled?: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className={`flex items-center justify-between text-sm text-slate-700 dark:text-slate-200 ${disabled ? "opacity-50" : ""}`}>
      {label}
      <input type="checkbox" role="switch" aria-label={label} checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-violet-600" />
    </label>
  );
}
