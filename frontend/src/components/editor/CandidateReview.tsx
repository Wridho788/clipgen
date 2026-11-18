"use client";

import { useState } from "react";
import { Check, Copy, MoveLeft, MoveRight, RotateCcw, X } from "lucide-react";

import { ClipResponse, RejectionReason } from "@/types/api";

export const REJECTION_LABELS: Record<RejectionReason, string> = {
  context_missing: "Konteks kurang",
  weak_moment: "Momen lemah",
  bad_boundaries: "Batas awal/akhir buruk",
  transcript_error: "Transkrip salah",
  repeated_content: "Konten berulang",
  poor_crop: "Crop/framing buruk",
  other: "Lainnya",
};

export const REVIEW_LABELS: Record<string, string> = {
  suggested: "Saran",
  accepted: "Diterima",
  rejected: "Ditolak",
  edited: "Diedit",
  exported: "Diekspor",
};

type CandidateReviewProps = {
  clip: ClipResponse;
  position: number;
  total: number;
  busy: boolean;
  onReview: (status: "suggested" | "accepted" | "rejected", reason?: RejectionReason) => void;
  onDuplicate: () => void;
  onMove: (direction: -1 | 1) => void;
};

export function CandidateReview({ clip, position, total, busy, onReview, onDuplicate, onMove }: CandidateReviewProps) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<RejectionReason>("weak_moment");
  const candidate = clip.candidate;
  const status = clip.review_status || "suggested";

  return (
    <section aria-label="Review kandidat" className="space-y-3 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Kandidat {position} / {total}</p>
          <p className="mt-0.5 text-sm text-slate-900 dark:text-slate-100" data-testid="candidate-rank">
            {candidate?.rank ? `Peringkat #${candidate.rank} dari ${candidate.total}` : "Tanpa peringkat"}
            <span className="ml-2 rounded-full border border-slate-300 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-700 dark:text-slate-300" data-testid="review-status">
              {REVIEW_LABELS[status] || status}
              {status === "rejected" && clip.review_reason ? ` · ${REJECTION_LABELS[clip.review_reason]}` : ""}
            </span>
          </p>
        </div>
        <div className="flex gap-1">
          <IconButton label="Geser ke kiri" disabled={busy || position <= 1} onClick={() => onMove(-1)}><MoveLeft className="h-4 w-4" /></IconButton>
          <IconButton label="Geser ke kanan" disabled={busy || position >= total} onClick={() => onMove(1)}><MoveRight className="h-4 w-4" /></IconButton>
          <IconButton label="Duplikat kandidat" disabled={busy} onClick={onDuplicate}><Copy className="h-4 w-4" /></IconButton>
        </div>
      </div>

      {candidate && (
        <div className="text-xs text-slate-600 dark:text-slate-300">
          {candidate.explanation.length > 0 && (
            <ul className="list-inside list-disc space-y-0.5">
              {candidate.explanation.map((reasonText) => <li key={reasonText}>{reasonText}</li>)}
            </ul>
          )}
          <p className="mt-1.5 text-[11px] text-ink-subtle">
            {candidate.score_meaning} Algoritma <span className="font-mono">{candidate.algorithm_version}</span>.
          </p>
        </div>
      )}

      {rejecting ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs text-slate-600 dark:text-slate-300">
            Alasan
            <select value={reason} onChange={(event) => setReason(event.target.value as RejectionReason)} className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950">
              {(Object.keys(REJECTION_LABELS) as RejectionReason[]).map((value) => <option key={value} value={value}>{REJECTION_LABELS[value]}</option>)}
            </select>
          </label>
          <button type="button" disabled={busy} onClick={() => { onReview("rejected", reason); setRejecting(false); }} className="rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">Tolak kandidat</button>
          <button type="button" onClick={() => setRejecting(false)} className="cg-btn min-h-9 px-3 py-1.5">Batal</button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={busy || status === "accepted"} onClick={() => onReview("accepted")} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-800 transition-colors duration-150 disabled:opacity-50 dark:border-emerald-400/40 dark:bg-emerald-400/10 dark:text-emerald-200">
            <Check className="h-4 w-4" /> Terima
          </button>
          <button type="button" disabled={busy} onClick={() => setRejecting(true)} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm font-medium text-rose-700 transition-colors duration-150 disabled:opacity-50 dark:border-rose-400/40 dark:bg-rose-400/10 dark:text-rose-200">
            <X className="h-4 w-4" /> Tolak…
          </button>
          {status !== "suggested" && (
            <button type="button" disabled={busy} onClick={() => onReview("suggested")} className="cg-btn min-h-9 px-3 py-1.5">
              <RotateCcw className="h-4 w-4" /> Reset review
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function IconButton({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} disabled={disabled} onClick={onClick} className="rounded-md border border-slate-300 p-1.5 text-slate-600 hover:border-slate-500 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300">
      {children}
    </button>
  );
}
