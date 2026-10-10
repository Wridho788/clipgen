"use client";

import { Film, Play, Sparkles } from "lucide-react";

import { ClipResponse } from "@/types/api";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/status";

type ClipGalleryProps = {
  clips: ClipResponse[];
  selectedClipId: string | null;
  onSelect: (clipId: string) => void;
};

/** A compact, scrollable browsing rail; full controls live in the selected editor. */
export function ClipGallery({ clips, selectedClipId, onSelect }: ClipGalleryProps) {
  return (
    <div className="-mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-3">
      {clips.map((clip, index) => {
        const selected = clip.id === selectedClipId;
        return (
          <button
            key={clip.id}
            type="button"
            onClick={() => onSelect(clip.id)}
            aria-pressed={selected}
            aria-label={`Pilih ${clip.title || `klip ${index + 1}`}`}
            className={`group relative w-32 shrink-0 snap-start overflow-hidden rounded-2xl border text-left shadow-sm transition sm:w-36 lg:w-40 ${
              selected
                ? "border-violet-400 ring-2 ring-violet-300/70 dark:border-violet-300 dark:ring-violet-300/40"
                : "border-slate-200 bg-slate-950 hover:-translate-y-0.5 hover:border-violet-300 dark:border-slate-700"
            }`}
          >
            <div className="relative aspect-[9/16] bg-slate-950">
              {clip.file_path ? (
                <video
                  src={api.getClipPreviewUrl(clip.id)}
                  muted
                  playsInline
                  preload="metadata"
                  className="h-full w-full object-cover opacity-90 transition duration-200 group-hover:scale-[1.03] group-hover:opacity-100"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-slate-400">
                  <Film className="h-5 w-5" />
                </div>
              )}
              <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-slate-950/90 via-slate-950/25 to-transparent" />
              <span className="absolute left-2 top-2 rounded-full bg-slate-950/75 px-2 py-1 text-[10px] font-semibold text-white">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="absolute bottom-2 left-2 text-[10px] font-medium text-white">
                {formatDuration(clip.start_time, clip.end_time)}
              </span>
              <span className="absolute bottom-2 right-2 flex h-7 w-7 items-center justify-center rounded-full bg-white/90 text-slate-950 shadow-sm">
                {selected ? <Sparkles className="h-3.5 w-3.5" /> : <Play className="ml-0.5 h-3.5 w-3.5 fill-current" />}
              </span>
            </div>
            <div className="bg-white px-2.5 py-2 dark:bg-slate-900">
              <p className="truncate text-xs font-semibold text-slate-800 dark:text-slate-100">
                {clip.title || `Klip ${index + 1}`}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
