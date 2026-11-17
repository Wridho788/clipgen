"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { AlertCircle, ClipboardPaste, Loader2, Save, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import {
  CampaignFormState,
  IMPORT_TEXT_LIMIT,
  ReviewRowId,
  formFromDraft,
  formToConfig,
  reviewRows,
  rowsNeedingReview,
  validateForm,
} from "@/lib/campaignForm";
import { CampaignImportDraft } from "@/types/api";
import { CampaignRulesForm } from "@/components/campaigns/CampaignRulesForm";

const primaryButton = "cg-btn-primary";

export function CampaignImport() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<CampaignImportDraft | null>(null);
  const [form, setForm] = useState<CampaignFormState | null>(null);
  const [acknowledged, setAcknowledged] = useState<ReviewRowId[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rows = useMemo(() => (draft ? reviewRows(draft) : null), [draft]);
  const pendingRows = useMemo(
    () => (rows ? rowsNeedingReview(rows).filter((id) => !acknowledged.includes(id)) : []),
    [rows, acknowledged],
  );
  const errors = useMemo(() => (form ? validateForm(form) : {}), [form]);
  const canSave = Boolean(form) && Object.keys(errors).length === 0 && pendingRows.length === 0 && !saving;

  const analyze = async () => {
    if (draft && !window.confirm("Analisa ulang akan mengganti semua isian yang sudah kamu ubah. Lanjutkan?")) return;
    setAnalyzing(true);
    setError(null);
    try {
      const result = await api.analyzeCampaignText(text);
      setDraft(result);
      setForm(formFromDraft(result));
      setAcknowledged([]);
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Gagal menganalisa teks campaign.");
    } finally {
      setAnalyzing(false);
    }
  };

  const save = async () => {
    if (!draft || !form || !canSave) return;
    setSaving(true);
    setError(null);
    try {
      const campaign = await api.createCampaign({
        name: form.name.trim(),
        type: "custom",
        source: "manual_import",
        config: formToConfig(form, undefined, draft.unresolved_items),
        raw_source_text: draft.raw_source_text,
        confirmed: true,
      });
      await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      router.push(`/campaigns/${campaign.id}`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Gagal menyimpan campaign.");
      setSaving(false);
    }
  };

  const overLimit = text.length > IMPORT_TEXT_LIMIT;

  return (
    <div className="space-y-6">
      <section className="clipgen-panel rounded-2xl p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand/15 text-brand-soft">
            <ClipboardPaste className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">1. Tempel teks campaign</h2>
            <p className="mt-1 text-sm leading-6 text-ink-muted">
              Salin brief dan semua detail dari situs campaign, lalu tempel di sini. ClipGen hanya membaca apa yang tertulis
              dan tidak menebak aturan yang tidak ada.
            </p>
          </div>
        </div>
        <label htmlFor="campaign-source-text" className="sr-only">Teks campaign</label>
        <textarea
          id="campaign-source-text"
          className="cg-input mt-4 min-h-64 resize-y leading-6"
          placeholder={"Contoh:\nCampaign Promo Ramadan\nDurasi 30-60 detik. Wajib pakai #Promo dan mention @akunresmi.\nCTA: Klik link di bio."}
          value={text}
          disabled={analyzing || saving}
          onChange={(event) => setText(event.target.value)}
        />
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className={`text-xs tabular-nums ${overLimit ? "font-medium text-amber-700 dark:text-amber-300" : "text-ink-muted"}`}>
            {text.length.toLocaleString("id-ID")} / {IMPORT_TEXT_LIMIT.toLocaleString("id-ID")} karakter
            {overLimit && " · bagian setelah batas ini tidak akan dianalisis"}
          </p>
          <button type="button" className={primaryButton} disabled={!text.trim() || analyzing || saving} onClick={analyze}>
            {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            {analyzing ? "Menganalisa…" : draft ? "Analisa ulang" : "Analisa Campaign"}
          </button>
        </div>
      </section>

      {error && (
        <div role="alert" className="flex items-start gap-2 cg-alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {draft && form && rows && (
        <section className="space-y-4" aria-label="Hasil analisis">
          <div>
            <h2 className="text-base font-semibold text-ink">2. Periksa dan koreksi</h2>
            <p className="mt-1 text-sm leading-6 text-ink-muted">
              Semua isian bisa diubah. Campaign belum tersimpan sampai kamu menekan “Konfirmasi &amp; Simpan”.
            </p>
          </div>

          {draft.warnings.map((warning) => (
            <p key={warning} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100">
              {warning}
            </p>
          ))}

          {draft.unresolved_items.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100">
              <p className="font-semibold">Perlu perhatian</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {draft.unresolved_items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          )}

          <DetectedInfo draft={draft} />

          <CampaignRulesForm
            form={form}
            onChange={(patch) => setForm((current) => (current ? { ...current, ...patch } : current))}
            errors={errors}
            rows={rows}
            acknowledged={acknowledged}
            onAcknowledge={(id, checked) =>
              setAcknowledged((current) => (checked ? [...current, id] : current.filter((item) => item !== id)))
            }
            disabled={saving}
          />

          <div className="clipgen-panel sticky bottom-4 flex flex-col gap-3 rounded-2xl p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-ink-muted" aria-live="polite">
              {pendingRows.length > 0
                ? `${pendingRows.length} bagian masih perlu kamu periksa dan centang.`
                : Object.keys(errors).length > 0
                  ? "Perbaiki isian yang bertanda merah."
                  : "Semua bagian sudah diperiksa."}
            </p>
            <button type="button" className={primaryButton} disabled={!canSave} onClick={save}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? "Menyimpan…" : "Konfirmasi & Simpan"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

/** Things the text mentions that are not rules ClipGen can check; kept visible, never turned into rules. */
function DetectedInfo({ draft }: { draft: CampaignImportDraft }) {
  const dates = Array.isArray(draft.fields.dates.value) ? draft.fields.dates.value : [];
  const urls = Array.isArray(draft.fields.source_urls.value) ? draft.fields.source_urls.value : [];
  if (dates.length === 0 && urls.length === 0) return null;
  return (
    <div className="clipgen-panel rounded-2xl p-4 text-sm text-ink-muted">
      <p className="font-semibold text-ink">Juga ditemukan di teks</p>
      {dates.length > 0 && <p className="mt-2">Tanggal: {dates.join(", ")}</p>}
      {urls.length > 0 && (
        <ul className="mt-2 space-y-1">
          {urls.map((url) => <li key={url} className="break-all">Tautan: {url}</li>)}
        </ul>
      )}
      <p className="mt-2 text-xs text-ink-muted">
        Informasi ini tidak diubah menjadi aturan. Teks aslinya tetap tersimpan bersama campaign.
      </p>
    </div>
  );
}
