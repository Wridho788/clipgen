"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ReactNode, useMemo, useState } from "react";
import { AlertCircle, Archive, ArchiveRestore, Copy, Loader2, Pencil, Save, X } from "lucide-react";
import { api } from "@/lib/api";
import { CampaignFormState, PLATFORM_OPTIONS, formFromConfig, formToConfig, validateForm } from "@/lib/campaignForm";
import { formatDateTime } from "@/lib/status";
import { CampaignConfiguration, CampaignDetail } from "@/types/api";
import { CampaignPageHeader } from "@/components/campaigns/CampaignPageHeader";
import { CampaignRulesForm } from "@/components/campaigns/CampaignRulesForm";

const buttonClass = "cg-btn";
const primaryButtonClass = "cg-btn-primary";

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;
  const queryClient = useQueryClient();
  const [editForm, setEditForm] = useState<CampaignFormState | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: campaign, isLoading, error } = useQuery<CampaignDetail>({
    queryKey: ["campaign", campaignId],
    queryFn: () => api.getCampaign(campaignId),
  });
  const { data: versions } = useQuery<CampaignConfiguration[]>({
    queryKey: ["campaign-versions", campaignId, campaign?.latest_version],
    queryFn: () => api.listCampaignVersions(campaignId),
    enabled: Boolean(campaign),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] }),
      queryClient.invalidateQueries({ queryKey: ["campaign-versions", campaignId] }),
      queryClient.invalidateQueries({ queryKey: ["campaigns"] }),
    ]);
  };

  const saveEdit = useMutation({
    mutationFn: (form: CampaignFormState) => {
      if (!campaign) throw new Error("Campaign belum dimuat");
      const { configuration } = campaign;
      return api.updateCampaign(campaignId, {
        name: form.name.trim(),
        config: formToConfig(form, configuration.config),
        raw_source_text: configuration.raw_source_text,
        confirmed: true,
      });
    },
    onSuccess: async () => {
      setEditForm(null);
      setSelectedVersion(null);
      setActionError(null);
      await refresh();
    },
    onError: (mutationError) => setActionError(mutationError instanceof Error ? mutationError.message : "Gagal menyimpan."),
  });

  const duplicate = useMutation({
    mutationFn: () => api.duplicateCampaign(campaignId),
    onSuccess: async (copy) => {
      await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      router.push(`/campaigns/${copy.id}`);
    },
    onError: (mutationError) => setActionError(mutationError instanceof Error ? mutationError.message : "Gagal menduplikat."),
  });

  const toggleArchive = useMutation({
    mutationFn: (archived: boolean) => api.setCampaignArchived(campaignId, archived),
    onSuccess: async () => {
      setActionError(null);
      await refresh();
    },
    onError: (mutationError) => setActionError(mutationError instanceof Error ? mutationError.message : "Gagal mengubah status."),
  });

  const errors = useMemo(() => (editForm ? validateForm(editForm) : {}), [editForm]);
  const shownVersion =
    versions?.find((item) => item.version === (selectedVersion ?? campaign?.latest_version)) ?? campaign?.configuration;

  if (isLoading) return <p className="text-sm text-ink-muted">Memuat campaign…</p>;
  if (error || !campaign) {
    return (
      <div className="space-y-4">
        <CampaignPageHeader backHref="/campaigns" backLabel="Semua campaign" title="Campaign tidak ditemukan" />
        <div role="alert" className="flex items-center gap-2 cg-alert">
          <AlertCircle className="h-4 w-4" />
          {error instanceof Error ? error.message : "Campaign tidak tersedia."}
        </div>
      </div>
    );
  }

  const archived = campaign.status === "archived";
  const editing = editForm !== null;

  return (
    <div className="space-y-6">
      <CampaignPageHeader
        backHref="/campaigns"
        backLabel="Semua campaign"
        title={campaign.name}
        description={`Versi ${campaign.latest_version} · ${campaign.source === "manual_import" ? "Diimpor dari teks" : campaign.source_name ?? "Dibuat manual"} · diperbarui ${formatDateTime(campaign.updated_at)}`}
        actions={
          !editing && (
            <>
              <button type="button" className={buttonClass} disabled={archived} onClick={() => setEditForm(formFromConfig(campaign.name, campaign.configuration.config))}>
                <Pencil className="h-4 w-4" />Edit aturan
              </button>
              <button type="button" className={buttonClass} disabled={duplicate.isPending} onClick={() => duplicate.mutate()}>
                {duplicate.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}Duplikat
              </button>
              <button type="button" className={buttonClass} disabled={toggleArchive.isPending} onClick={() => toggleArchive.mutate(!archived)}>
                {archived ? <ArchiveRestore className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
                {archived ? "Aktifkan kembali" : "Arsipkan"}
              </button>
            </>
          )
        }
      />

      <div className="flex flex-wrap gap-2">
        {archived && <Tag tone="slate">Diarsipkan: tidak bisa dipakai untuk video baru</Tag>}
        {!campaign.confirmed && <Tag tone="amber">Versi terbaru belum dikonfirmasi</Tag>}
        {campaign.confirmed && <Tag tone="emerald">Dikonfirmasi pengguna</Tag>}
      </div>

      {actionError && (
        <div role="alert" className="flex items-center gap-2 cg-alert">
          <AlertCircle className="h-4 w-4" />{actionError}
        </div>
      )}

      {editing && editForm ? (
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            Menyimpan akan membuat <strong>versi {campaign.latest_version + 1}</strong>. Versi sebelumnya tetap tersimpan, dan job yang sudah dibuat tidak berubah.
          </p>
          <CampaignRulesForm
            form={editForm}
            onChange={(patch) => setEditForm((current) => (current ? { ...current, ...patch } : current))}
            errors={errors}
            disabled={saveEdit.isPending}
          />
          <div className="flex flex-wrap gap-2">
            <button type="button" className={primaryButtonClass} disabled={Object.keys(errors).length > 0 || saveEdit.isPending} onClick={() => saveEdit.mutate(editForm)}>
              {saveEdit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Simpan sebagai versi baru
            </button>
            <button type="button" className={buttonClass} disabled={saveEdit.isPending} onClick={() => { setEditForm(null); setActionError(null); }}>
              <X className="h-4 w-4" />Batal
            </button>
          </div>
        </div>
      ) : (
        shownVersion && (
          <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
            <ConfigView configuration={shownVersion} isLatest={shownVersion.version === campaign.latest_version} />
            <VersionList
              versions={versions ?? [campaign.configuration]}
              selected={shownVersion.version}
              latest={campaign.latest_version}
              onSelect={setSelectedVersion}
            />
          </div>
        )
      )}
    </div>
  );
}

function ConfigView({ configuration, isLatest }: { configuration: CampaignConfiguration; isLatest: boolean }) {
  const { config } = configuration;
  const { rules } = config;
  const platforms = (config.platforms.length > 0 ? config.platforms : rules.platforms).map(
    (value) => PLATFORM_OPTIONS.find((option) => option.value === value)?.label ?? value,
  );
  return (
    <div className="space-y-4">
      {!isLatest && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100">
          Kamu sedang melihat versi {configuration.version}, bukan versi terbaru.
        </p>
      )}

      <Card title="Brief & tujuan">
        <Row label="Tujuan" value={config.objective} />
        <Row label="Brief" value={config.brief} multiline />
        <Row label="Target audiens" value={config.target_audience} />
      </Card>

      <Card title="Aturan wajib">
        <Row label="Durasi klip" value={`${rules.min_clip_seconds}–${rules.max_clip_seconds} detik`} />
        <Row label="Platform" value={platforms.join(", ")} />
        <Row label="Hashtag" value={rules.hashtags.map((tag) => `#${tag}`).join(" ")} />
        <Row label="Mention" value={rules.mentions.join(" ")} />
        <Row label="Frasa wajib" value={rules.required_phrases.join(", ")} />
        <Row label="Kata terlarang" value={rules.prohibited_terms.join(", ")} />
        <Row label="CTA" value={rules.cta ?? ""} />
      </Card>

      <Card title="Preferensi">
        {config.soft_preferences.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
            {config.soft_preferences.map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : (
          <Empty />
        )}
      </Card>

      <Card title="Reward & submission">
        <Row label="Catatan reward" value={config.reward_details ?? ""} multiline />
        <p className="text-xs text-ink-muted">ClipGen tidak memverifikasi hadiah, syarat, atau kelayakan campaign.</p>
      </Card>

      {config.unresolved_items.length > 0 && (
        <Card title="Belum terverifikasi">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
            {config.unresolved_items.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Card>
      )}

      <details className="clipgen-panel rounded-2xl p-4">
        <summary className="cursor-pointer text-sm font-semibold text-ink">Teks mentah yang diimpor</summary>
        {configuration.raw_source_text ? (
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-ink-muted">{configuration.raw_source_text}</pre>
        ) : (
          <p className="mt-3 text-sm text-ink-muted">Tidak ada teks mentah untuk versi ini.</p>
        )}
      </details>
    </div>
  );
}

function VersionList({
  versions,
  selected,
  latest,
  onSelect,
}: {
  versions: CampaignConfiguration[];
  selected: number;
  latest: number;
  onSelect: (version: number) => void;
}) {
  return (
    <aside className="clipgen-panel h-fit rounded-2xl p-4" aria-label="Riwayat versi">
      <h2 className="text-sm font-semibold text-ink">Riwayat versi</h2>
      <ul className="mt-3 space-y-1">
        {[...versions].reverse().map((item) => (
          <li key={item.version}>
            <button
              type="button"
              aria-current={item.version === selected}
              onClick={() => onSelect(item.version)}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                item.version === selected
                  ? "bg-violet-50 text-violet-900 dark:bg-violet-400/10 dark:text-violet-100"
                  : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800/60"
              }`}
            >
              <span className="font-medium tabular-nums">Versi {item.version}</span>
              {item.version === latest && <span className="ml-2 text-xs text-ink-muted">terbaru</span>}
              <span className="mt-0.5 block text-xs text-ink-muted">
                {formatDateTime(item.created_at)} · {item.user_confirmed_at ? "dikonfirmasi" : "belum dikonfirmasi"}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs leading-5 text-ink-muted">
        Job menyimpan versi yang dipakai saat dibuat, jadi mengedit campaign tidak mengubah hasil lama.
      </p>
    </aside>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="clipgen-panel rounded-2xl p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <div className="mt-3 space-y-2">{children}</div>
    </section>
  );
}

function Row({ label, value, multiline = false }: { label: string; value: string; multiline?: boolean }) {
  return (
    <div className="grid gap-1 text-sm sm:grid-cols-[9rem_1fr]">
      <span className="text-ink-muted">{label}</span>
      <span className={`text-ink ${multiline ? "whitespace-pre-wrap" : ""}`}>
        {value.trim() ? value : <Empty />}
      </span>
    </div>
  );
}

function Empty() {
  return <span className="text-ink-subtle">Tidak ada</span>;
}

function Tag({ tone, children }: { tone: "slate" | "amber" | "emerald"; children: string }) {
  const className = {
    slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    amber: "bg-amber-50 text-amber-800 dark:bg-amber-400/10 dark:text-amber-200",
    emerald: "bg-emerald-50 text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-200",
  }[tone];
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${className}`}>{children}</span>;
}
