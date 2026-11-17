"use client";

import { ReactNode } from "react";
import { CampaignPlatform, ExtractedFieldStatus } from "@/types/api";
import {
  CampaignFormErrors,
  CampaignFormState,
  PLATFORM_OPTIONS,
  ReviewRowId,
  ReviewRowMeta,
} from "@/lib/campaignForm";

const inputClass = "cg-input";

const numberInputClass = "cg-input w-24 tabular-nums";

const STATUS_STYLES: Record<ExtractedFieldStatus, { label: string; className: string }> = {
  found: {
    label: "Ditemukan",
    className: "bg-emerald-50 text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-200",
  },
  needs_review: {
    label: "Perlu review",
    className: "bg-amber-50 text-amber-800 dark:bg-amber-400/10 dark:text-amber-200",
  },
  not_provided: {
    label: "Tidak ada",
    className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  },
};

export function StatusBadge({ status }: { status: ExtractedFieldStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${style.className}`}>
      {style.label}
    </span>
  );
}

interface CampaignRulesFormProps {
  form: CampaignFormState;
  onChange: (patch: Partial<CampaignFormState>) => void;
  errors: CampaignFormErrors;
  /** Import review only: what the text said about each row. */
  rows?: Record<ReviewRowId, ReviewRowMeta>;
  acknowledged?: ReviewRowId[];
  onAcknowledge?: (id: ReviewRowId, checked: boolean) => void;
  disabled?: boolean;
}

export function CampaignRulesForm({
  form,
  onChange,
  errors,
  rows,
  acknowledged = [],
  onAcknowledge,
  disabled = false,
}: CampaignRulesFormProps) {
  const togglePlatform = (platform: CampaignPlatform) => {
    const next = form.platforms.includes(platform)
      ? form.platforms.filter((item) => item !== platform)
      : [...form.platforms, platform];
    onChange({ platforms: next });
  };

  const row = (id: ReviewRowId) =>
    rows ? { meta: rows[id], acknowledged: acknowledged.includes(id), onAcknowledge: onAcknowledge && ((checked: boolean) => onAcknowledge(id, checked)) } : undefined;

  return (
    <div className="space-y-5">
      <Section title="Informasi campaign" description="Ringkasan yang membantu kamu mengenali campaign ini nanti.">
        <Field label="Nama campaign" htmlFor="campaign-name" error={errors.name}>
          <input
            id="campaign-name"
            className={inputClass}
            value={form.name}
            maxLength={120}
            disabled={disabled}
            onChange={(event) => onChange({ name: event.target.value })}
          />
        </Field>
        <Field label="Tujuan" htmlFor="campaign-objective" hint="Opsional. Apa yang ingin dicapai campaign ini?">
          <input
            id="campaign-objective"
            className={inputClass}
            value={form.objective}
            maxLength={1000}
            disabled={disabled}
            onChange={(event) => onChange({ objective: event.target.value })}
          />
        </Field>
        <Field label="Brief" htmlFor="campaign-brief" hint="Opsional. Salin bagian brief yang ingin kamu lihat kembali.">
          <textarea
            id="campaign-brief"
            className={`${inputClass} min-h-24 resize-y`}
            value={form.brief}
            maxLength={8000}
            disabled={disabled}
            onChange={(event) => onChange({ brief: event.target.value })}
          />
        </Field>
        <Field label="Target audiens" htmlFor="campaign-audience">
          <input
            id="campaign-audience"
            className={inputClass}
            value={form.targetAudience}
            maxLength={500}
            disabled={disabled}
            onChange={(event) => onChange({ targetAudience: event.target.value })}
          />
        </Field>
      </Section>

      <Section
        title="Aturan wajib"
        description="Aturan yang bisa dicek otomatis. Dipakai untuk membatasi durasi klip dan memeriksa hasilnya."
      >
        <Field
          label="Durasi klip (detik)"
          htmlFor="campaign-min-seconds"
          error={errors.duration}
          row={row("duration")}
          notProvidedHint="Teks tidak menyebut durasi. Memakai default ClipGen; ubah jika perlu."
        >
          <div className="flex items-center gap-2">
            <input
              id="campaign-min-seconds"
              aria-label="Durasi minimum (detik)"
              inputMode="numeric"
              className={numberInputClass}
              value={form.minSeconds}
              disabled={disabled}
              onChange={(event) => onChange({ minSeconds: event.target.value })}
            />
            <span className="text-sm text-ink-muted">sampai</span>
            <input
              id="campaign-max-seconds"
              aria-label="Durasi maksimum (detik)"
              inputMode="numeric"
              className={numberInputClass}
              value={form.maxSeconds}
              disabled={disabled}
              onChange={(event) => onChange({ maxSeconds: event.target.value })}
            />
            <span className="text-sm text-ink-muted">detik</span>
          </div>
        </Field>

        <Field label="Platform" row={row("platforms")} notProvidedHint="Teks tidak menyebut platform.">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Platform">
            {PLATFORM_OPTIONS.map((option) => {
              const active = form.platforms.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={active}
                  disabled={disabled}
                  onClick={() => togglePlatform(option.value)}
                  className={`inline-flex min-h-10 items-center rounded-full border px-3 py-1.5 text-sm transition-colors disabled:opacity-60 ${
                    active
                      ? "border-violet-400 bg-violet-50 text-violet-900 dark:border-violet-300/70 dark:bg-violet-400/10 dark:text-violet-100"
                      : "border-slate-200 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </Field>

        <Field
          label="Hashtag wajib"
          htmlFor="campaign-hashtags"
          hint="Pisahkan dengan koma. Tanda # tidak perlu."
          row={row("hashtags")}
          notProvidedHint="Teks tidak menyebut hashtag."
        >
          <input
            id="campaign-hashtags"
            className={inputClass}
            value={form.hashtags}
            disabled={disabled}
            onChange={(event) => onChange({ hashtags: event.target.value })}
          />
        </Field>

        <Field
          label="Mention wajib"
          htmlFor="campaign-mentions"
          hint="Pisahkan dengan koma, contoh: @akun_resmi"
          row={row("mentions")}
          notProvidedHint="Teks tidak menyebut mention."
        >
          <input
            id="campaign-mentions"
            className={inputClass}
            value={form.mentions}
            disabled={disabled}
            onChange={(event) => onChange({ mentions: event.target.value })}
          />
        </Field>

        <Field label="Frasa wajib" htmlFor="campaign-phrases" hint="Kalimat atau kata yang harus muncul. Pisahkan dengan koma.">
          <input
            id="campaign-phrases"
            className={inputClass}
            value={form.requiredPhrases}
            disabled={disabled}
            onChange={(event) => onChange({ requiredPhrases: event.target.value })}
          />
        </Field>

        <Field
          label="Kata terlarang"
          htmlFor="campaign-prohibited"
          hint="Pisahkan dengan koma."
          row={row("prohibited_terms")}
          notProvidedHint="Teks tidak menyebut larangan."
        >
          <input
            id="campaign-prohibited"
            className={inputClass}
            value={form.prohibitedTerms}
            disabled={disabled}
            onChange={(event) => onChange({ prohibitedTerms: event.target.value })}
          />
        </Field>

        <Field label="CTA" htmlFor="campaign-cta" row={row("cta")} notProvidedHint="Teks tidak menyebut CTA berlabel.">
          <input
            id="campaign-cta"
            className={inputClass}
            value={form.cta}
            maxLength={300}
            disabled={disabled}
            onChange={(event) => onChange({ cta: event.target.value })}
          />
        </Field>
      </Section>

      <Section
        title="Preferensi"
        description="Panduan gaya yang diinginkan, bukan aturan yang bisa dicek otomatis."
      >
        <Field label="Gaya yang diinginkan" htmlFor="campaign-soft" hint="Satu preferensi per baris, contoh: hook humor, tempo cepat.">
          <textarea
            id="campaign-soft"
            className={`${inputClass} min-h-20 resize-y`}
            value={form.softPreferences}
            disabled={disabled}
            onChange={(event) => onChange({ softPreferences: event.target.value })}
          />
        </Field>
      </Section>

      <Section
        title="Reward & submission"
        description="Catatan saja. ClipGen tidak memverifikasi hadiah, syarat, atau kelayakan campaign."
      >
        <Field label="Catatan reward" htmlFor="campaign-reward">
          <textarea
            id="campaign-reward"
            className={`${inputClass} min-h-20 resize-y`}
            value={form.rewardDetails}
            maxLength={4000}
            disabled={disabled}
            onChange={(event) => onChange({ rewardDetails: event.target.value })}
          />
        </Field>
      </Section>
    </div>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="clipgen-panel rounded-2xl p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{description}</p>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

interface FieldRow {
  meta: ReviewRowMeta;
  acknowledged: boolean;
  onAcknowledge?: (checked: boolean) => void;
}

function Field({
  label,
  htmlFor,
  hint,
  error,
  row,
  notProvidedHint,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  row?: FieldRow;
  notProvidedHint?: string;
  children: ReactNode;
}) {
  const needsReview = row?.meta.status === "needs_review";
  return (
    <div className={needsReview ? "rounded-xl border border-amber-200 bg-amber-50/50 p-3 dark:border-amber-400/30 dark:bg-amber-400/5" : undefined}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="text-sm font-medium text-ink">{label}</label>
        ) : (
          <span className="text-sm font-medium text-ink">{label}</span>
        )}
        {row && <StatusBadge status={row.meta.status} />}
      </div>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-ink-muted">{hint}</p>}
      {error && <p role="alert" className="mt-1.5 text-xs font-medium text-rose-600 dark:text-rose-300">{error}</p>}
      {row?.meta.status === "not_provided" && notProvidedHint && (
        <p className="mt-1.5 text-xs text-ink-muted">{notProvidedHint}</p>
      )}
      {row && row.meta.evidence.length > 0 && (
        <p className="mt-1.5 text-xs text-ink-muted">
          Dari teks: {row.meta.evidence.map((quote) => `“${quote}”`).join(" · ")}
        </p>
      )}
      {row?.meta.notes.map((note) => (
        <p key={note} className="mt-1.5 text-xs font-medium text-amber-800 dark:text-amber-200">{note}</p>
      ))}
      {needsReview && row.onAcknowledge && (
        <label className="mt-1 flex min-h-10 cursor-pointer items-center gap-2 text-xs font-medium text-ink">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-line-strong bg-canvas accent-brand"
            checked={row.acknowledged}
            onChange={(event) => row.onAcknowledge?.(event.target.checked)}
          />
          Saya sudah memeriksa bagian “{label}”
        </label>
      )}
    </div>
  );
}
