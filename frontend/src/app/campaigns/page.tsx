"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AlertCircle, ArrowRight, BriefcaseBusiness, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/status";
import { CampaignSummary } from "@/types/api";
import { CampaignPageHeader } from "@/components/campaigns/CampaignPageHeader";

export default function CampaignsPage() {
  const [showArchived, setShowArchived] = useState(false);
  const { data: campaigns, isLoading, error } = useQuery<CampaignSummary[]>({
    queryKey: ["campaigns", { showArchived }],
    queryFn: () => api.listCampaigns(showArchived),
  });

  return (
    <div className="space-y-6">
      <CampaignPageHeader
        backHref="/"
        backLabel="Dashboard"
        title="Campaign"
        description="Aturan campaign yang tersimpan. Setiap perubahan dibuat sebagai versi baru, jadi job lama tetap memakai aturan saat dibuat."
        actions={
          <Link
            href="/campaigns/new"
            className="cg-btn-primary"
          >
            <Plus className="h-4 w-4" />
            Import campaign
          </Link>
        }
      />

      <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 text-sm text-ink-muted">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-line-strong bg-canvas accent-brand"
          checked={showArchived}
          onChange={(event) => setShowArchived(event.target.checked)}
        />
        Tampilkan yang diarsipkan
      </label>

      {error && (
        <div role="alert" className="flex items-center gap-2 cg-alert">
          <AlertCircle className="h-4 w-4" />
          {error instanceof Error ? error.message : "Gagal memuat campaign"}
        </div>
      )}

      {isLoading && (
        <div className="grid gap-3 lg:grid-cols-2">
          {[0, 1].map((item) => (
            <div key={item} className="clipgen-panel rounded-2xl p-4">
              <div className="h-4 w-48 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
              <div className="mt-3 h-3 w-28 animate-pulse rounded bg-slate-100 dark:bg-slate-900" />
            </div>
          ))}
        </div>
      )}

      {!isLoading && !error && campaigns && campaigns.length === 0 && (
        <div className="clipgen-panel rounded-2xl px-4 py-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/15 text-brand-soft">
            <BriefcaseBusiness className="h-5 w-5" />
          </div>
          <p className="mt-4 font-semibold text-ink">Belum ada campaign</p>
          <p className="mt-1 text-sm text-ink-muted">Tempel teks dari situs campaign untuk membuat yang pertama.</p>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        {campaigns?.map((campaign) => <CampaignCard key={campaign.id} campaign={campaign} />)}
      </div>
    </div>
  );
}

function CampaignCard({ campaign }: { campaign: CampaignSummary }) {
  return (
    <Link
      href={`/campaigns/${campaign.id}`}
      className="clipgen-panel group rounded-2xl p-4 transition-colors hover:border-violet-300 dark:hover:border-violet-300/60"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
          <BriefcaseBusiness className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-semibold text-ink">{campaign.name}</span>
            {campaign.status === "archived" && <Pill tone="slate">Diarsipkan</Pill>}
            {!campaign.confirmed && <Pill tone="amber">Belum dikonfirmasi</Pill>}
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            Versi {campaign.latest_version} · {campaign.source === "manual_import" ? "Import teks" : campaign.source_name ?? "Dibuat manual"} ·{" "}
            {formatDateTime(campaign.updated_at)}
          </p>
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-slate-400 transition-colors group-hover:text-violet-600" />
      </div>
    </Link>
  );
}

function Pill({ tone, children }: { tone: "slate" | "amber"; children: string }) {
  const className =
    tone === "amber"
      ? "bg-amber-50 text-amber-800 dark:bg-amber-400/10 dark:text-amber-200"
      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>{children}</span>;
}
