"use client";

import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, OctagonX } from "lucide-react";
import { CampaignBrief, CampaignCompliance, ClipEdit } from "@/types/api";

/** Backend statuses plus `unknown`, which it does not emit yet (docs/11 D2). */
type CheckStatus = "pass" | "review_required" | "blocked" | "unknown";

const GROUPS: Array<{ status: CheckStatus; heading: string; icon: ReactNode; className: string }> = [
  {
    status: "blocked",
    heading: "Gagal",
    icon: <OctagonX className="h-4 w-4" aria-hidden />,
    className: "text-rose-600 dark:text-rose-300",
  },
  {
    status: "review_required",
    heading: "Perlu review",
    icon: <AlertTriangle className="h-4 w-4" aria-hidden />,
    className: "text-amber-700 dark:text-amber-300",
  },
  {
    status: "unknown",
    heading: "Belum bisa dicek",
    icon: <CircleHelp className="h-4 w-4" aria-hidden />,
    className: "text-ink-muted",
  },
  {
    status: "pass",
    heading: "Lolos",
    icon: <CheckCircle2 className="h-4 w-4" aria-hidden />,
    className: "text-emerald-600 dark:text-emerald-300",
  },
];

function seconds(value: number): string {
  return value.toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

/**
 * Campaign rules in force for this clip, plus the backend's compliance
 * findings. Findings are grouped by status and never summarised as a
 * percentage: compliance is a checklist, not a score.
 */
export function CampaignPanel({
  brief,
  compliance,
  draft,
}: {
  brief: CampaignBrief;
  compliance: CampaignCompliance | null;
  draft: ClipEdit | null;
}) {
  const allChecks = (compliance?.checks ?? []) as Array<{ key: string; label: string; status: CheckStatus; detail: string }>;
  // The backend's duration check reflects the last save; the live line below is
  // computed from the unsaved draft. Showing both means two slightly different
  // numbers on screen, so the live one wins and this one is dropped.
  const checks = allChecks.filter((check) => check.key !== "duration");
  // Duration is the one rule that changes continuously while trimming, so it is
  // recomputed from the unsaved draft; every other check comes from the backend
  // and refreshes on autosave.
  const durationSeconds = draft ? Math.max(0, (draft.trim_end_ms - draft.trim_start_ms) / 1000) : null;
  const inRange =
    durationSeconds !== null && durationSeconds >= brief.min_clip_seconds && durationSeconds <= brief.max_clip_seconds;
  const range = `${brief.min_clip_seconds}–${brief.max_clip_seconds} detik`;

  return (
    <div className="space-y-4 text-sm">
      <section>
        <p className="cg-eyebrow">Aturan aktif</p>
        <h3 className="mt-1 font-semibold text-ink">{brief.name}</h3>
        <dl className="mt-2 space-y-1.5">
          <Rule label="Durasi">{range}</Rule>
          {brief.required_phrases.length > 0 && <Rule label="Frasa wajib">{brief.required_phrases.join(", ")}</Rule>}
          {brief.hashtags.length > 0 && <Rule label="Hashtag">{brief.hashtags.map((tag) => `#${tag}`).join(" ")}</Rule>}
          {brief.mentions.length > 0 && <Rule label="Mention">{brief.mentions.join(" ")}</Rule>}
          {brief.prohibited_terms.length > 0 && <Rule label="Kata terlarang">{brief.prohibited_terms.join(", ")}</Rule>}
          {brief.cta && <Rule label="CTA">{brief.cta}</Rule>}
          {brief.required_visuals.length > 0 && <Rule label="Visual wajib">{brief.required_visuals.join(", ")}</Rule>}
        </dl>
      </section>

      <p
        data-testid="campaign-live-duration"
        className={durationSeconds === null ? "cg-alert-info" : inRange ? "cg-alert-info" : "cg-alert-warn"}
      >
        {durationSeconds === null ? (
          <>Durasi klip belum bisa dibaca.</>
        ) : inRange ? (
          <>
            Durasi saat ini <strong className="tabular-nums">{seconds(durationSeconds)} detik</strong>, sesuai batas {range}.
          </>
        ) : (
          <>
            Durasi saat ini <strong className="tabular-nums">{seconds(durationSeconds)} detik</strong>, di luar batas {range}.
          </>
        )}
      </p>

      <section>
        <p className="cg-eyebrow">Kepatuhan campaign</p>
        {checks.length === 0 ? (
          <p className="mt-2 text-ink-muted">Belum ada hasil pemeriksaan untuk klip ini.</p>
        ) : (
          <div className="mt-2 space-y-3">
            {GROUPS.map((group) => {
              const items = checks.filter((check) => check.status === group.status);
              if (items.length === 0) return null;
              return (
                <div key={group.status}>
                  <h4 className={`flex items-center gap-1.5 text-xs font-semibold ${group.className}`}>
                    {group.icon}
                    {group.heading} ({items.length})
                  </h4>
                  <ul className="mt-1.5 space-y-1.5">
                    {items.map((check) => (
                      <li key={check.key} className="rounded-lg border border-line px-3 py-2">
                        <p className="font-medium text-ink">{check.label}</p>
                        <p className="mt-0.5 text-ink-muted">{check.detail}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-3 text-xs leading-5 text-ink-subtle">
          Pemeriksaan ini hanya membandingkan klip dengan aturan yang kamu simpan. Lolos di sini tidak menjamin klip
          diterima, memenuhi syarat hadiah, atau mendapat views.
        </p>
      </section>
    </div>
  );
}

function Rule({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[7rem_1fr]">
      <dt className="text-ink-subtle">{label}</dt>
      <dd className="text-ink">{children}</dd>
    </div>
  );
}
