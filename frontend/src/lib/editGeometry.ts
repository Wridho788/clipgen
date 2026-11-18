// Preview geometry mirrored from backend/app/core/pipeline/render_plan.py and
// backend/app/core/edit_model.py. Keep both sides in sync: the preview must
// describe the same frame the FFmpeg export will produce.
import { CaptionCue, ClipEdit, OutputPreset } from "@/types/api";

export const PRESET_DIMENSIONS: Record<Exclude<OutputPreset, "original">, [number, number]> = {
  tiktok: [1080, 1920],
  reels: [1080, 1920],
  youtube_shorts: [1080, 1920],
  square: [1080, 1080],
  landscape: [1920, 1080],
};

export const PRESET_LABELS: Record<OutputPreset, string> = {
  original: "Original (rasio sumber)",
  tiktok: "TikTok 9:16",
  reels: "Reels 9:16",
  youtube_shorts: "YouTube Shorts 9:16",
  square: "Square 1:1",
  landscape: "Landscape 16:9",
};

export const MIN_CLIP_MS = 5_000;
export const MAX_CLIP_MS = 120_000;
export const ZOOM_FACTOR = 1.12;

export function outputDimensions(edit: ClipEdit, sourceWidth?: number, sourceHeight?: number): [number, number] {
  if (edit.output_preset !== "original") return PRESET_DIMENSIONS[edit.output_preset];
  const even = (value: number) => Math.max(2, value - (value % 2));
  return [even(sourceWidth || 1920), even(sourceHeight || 1080)];
}

/** Caption font scale: ``font_size`` is defined for a 1080 px short edge. */
export function captionScale(width: number, height: number): number {
  return Math.min(width, height) / 1080;
}

/** Greedy word wrap — same algorithm as ``wrap_caption_text`` in Python. */
export function wrapCaptionText(text: string, maxChars: number): string[] {
  const lines: string[] = [];
  let current = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const candidate = current ? `${current} ${word}` : word;
    if (current && candidate.length > maxChars) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return lines;
}

/** Cues the export will burn in, clamped to the trim (documented trim policy). */
export function renderedCues(edit: ClipEdit): CaptionCue[] {
  if (!edit.captions.enabled) return [];
  return [...edit.captions.cues]
    .sort((a, b) => a.start_ms - b.start_ms)
    .filter((cue) => cue.text.trim())
    .map((cue) => ({
      ...cue,
      start_ms: Math.max(cue.start_ms, edit.trim_start_ms),
      end_ms: Math.min(cue.end_ms, edit.trim_end_ms),
    }))
    .filter((cue) => cue.end_ms - cue.start_ms >= 40);
}

export function cueOutsideTrim(cue: CaptionCue, edit: ClipEdit): boolean {
  return cue.end_ms <= edit.trim_start_ms || cue.start_ms >= edit.trim_end_ms;
}

export function activeCue(cues: CaptionCue[], sourceMs: number): CaptionCue | null {
  return cues.find((cue) => sourceMs >= cue.start_ms && sourceMs < cue.end_ms) || null;
}

export function validateTrim(edit: ClipEdit, sourceDurationMs?: number | null): string | null {
  const duration = edit.trim_end_ms - edit.trim_start_ms;
  if (edit.trim_start_ms < 0) return "Waktu mulai tidak boleh negatif.";
  if (duration < MIN_CLIP_MS) return `Durasi klip minimal ${MIN_CLIP_MS / 1000} detik.`;
  if (duration > MAX_CLIP_MS) return `Durasi klip maksimal ${MAX_CLIP_MS / 1000} detik.`;
  if (sourceDurationMs && edit.trim_end_ms > sourceDurationMs) return "Waktu akhir melebihi durasi video sumber.";
  return null;
}

export function formatClock(ms: number): string {
  const safe = Math.max(0, Math.round(ms));
  const minutes = Math.floor(safe / 60_000);
  const seconds = Math.floor((safe % 60_000) / 1000);
  const tenths = Math.floor((safe % 1000) / 100);
  return `${minutes}:${String(seconds).padStart(2, "0")}.${tenths}`;
}

export function parseClock(value: string): number | null {
  const trimmed = value.trim();
  const match = trimmed.match(/^(?:(\d+):)?(\d+(?:\.\d+)?)$/);
  if (!match) return null;
  const minutes = match[1] ? Number(match[1]) : 0;
  const seconds = Number(match[2]);
  if (!Number.isFinite(seconds)) return null;
  return Math.round((minutes * 60 + seconds) * 1000);
}

export function newCueId(): string {
  return Math.random().toString(16).slice(2, 14).padEnd(12, "0");
}
