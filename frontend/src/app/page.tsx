"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertCircle, ArrowRight, BriefcaseBusiness, Clock3, FolderOpen, Plus, RefreshCw, Search } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime, isActiveJobStatus, isTerminalJobStatus, JOB_STATUS_LABELS, JOB_STATUS_TONES } from "@/lib/status";
import { CampaignSummary, JobResponse, JobStatus } from "@/types/api";
import { VideoUpload } from "@/components/VideoUpload";
import { SystemStatusBar } from "@/components/SystemStatusBar";
import { StorageClearControl } from "@/components/StorageClearControl";

type JobFilter = "all" | "active" | Extract<JobStatus, "done" | "failed" | "cancelled">;
const JOB_FILTERS: { value: JobFilter; label: string }[] = [
  { value: "all", label: "Semua" }, { value: "active", label: "Aktif" }, { value: "done", label: "Selesai" },
  { value: "failed", label: "Gagal" }, { value: "cancelled", label: "Batal" },
];

export default function Dashboard() {
  const [filter, setFilter] = useState<JobFilter>("all");
  const { data: jobs, isLoading, isFetching, error, refetch } = useQuery<JobResponse[]>({
    queryKey: ["jobs"], queryFn: () => api.listJobs(), refetchIntervalInBackground: true, refetchOnWindowFocus: true,
    refetchInterval: (query) => query.state.data?.some((job) => !isTerminalJobStatus(job.status)) ? 3000 : false,
  });
  // Archived campaigns are included so older projects can still show which campaign they used.
  const { data: campaigns } = useQuery<CampaignSummary[]>({
    queryKey: ["campaigns", { showArchived: true }], queryFn: () => api.listCampaigns(true),
  });
  const campaignNames = useMemo(() => new Map((campaigns ?? []).map((campaign) => [campaign.id, campaign.name])), [campaigns]);
  const activeCampaigns = useMemo(() => (campaigns ?? []).filter((campaign) => campaign.status === "active"), [campaigns]);
  const recentCampaigns = activeCampaigns.slice(0, 4);
  const activeCampaignCount = activeCampaigns.length;

  const filteredJobs = useMemo(() => {
    const list = jobs || [];
    if (filter === "all") return list;
    if (filter === "active") return list.filter((job) => isActiveJobStatus(job.status));
    return list.filter((job) => job.status === filter);
  }, [filter, jobs]);
  const counts = useMemo(() => {
    const list = jobs || [];
    return { all: list.length, active: list.filter((job) => isActiveJobStatus(job.status)).length, done: list.filter((job) => job.status === "done").length, failed: list.filter((job) => job.status === "failed").length, cancelled: list.filter((job) => job.status === "cancelled").length };
  }, [jobs]);

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="cg-eyebrow">Workspace</p>
          <h1 className="mt-1 text-3xl font-semibold text-ink">Proyek</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
            Ubah video panjang menjadi klip short-form. Pilih campaign supaya aturannya ikut menjaga durasi, hashtag, dan metadata.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StorageClearControl />
          <button type="button" onClick={() => refetch()} className="cg-btn" title="Muat ulang proyek">
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />Refresh
          </button>
        </div>
      </header>

      <section aria-label="Ringkasan" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Sedang diproses" value={counts.active} tone="accent" />
        <StatTile label="Selesai" value={counts.done} tone="good" />
        <StatTile label="Gagal" value={counts.failed} tone={counts.failed > 0 ? "bad" : "muted"} />
        <StatTile label="Campaign aktif" value={activeCampaignCount} tone="brand" href="/campaigns" />
      </section>

      <section className="space-y-3" aria-labelledby="new-project-heading">
        <div className="flex items-center gap-2">
          <Plus className="h-4 w-4 text-brand-soft" aria-hidden />
          <h2 id="new-project-heading" className="text-lg font-semibold text-ink">Proyek baru</h2>
        </div>
        <VideoUpload />
      </section>

      {recentCampaigns.length > 0 && (
        <section className="space-y-3" aria-labelledby="recent-campaigns-heading">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <BriefcaseBusiness className="h-4 w-4 text-brand-soft" aria-hidden />
              <h2 id="recent-campaigns-heading" className="text-lg font-semibold text-ink">Campaign terbaru</h2>
            </div>
            <Link href="/campaigns" className="inline-flex min-h-10 items-center gap-1 text-sm font-medium text-brand-soft transition-colors hover:text-ink">
              Semua campaign<ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {recentCampaigns.map((campaign) => (
              <Link key={campaign.id} href={`/campaigns/${campaign.id}`} className="clipgen-panel rounded-panel p-4 transition-colors duration-150 hover:border-brand/60">
                <p className="truncate text-sm font-semibold text-ink">{campaign.name}</p>
                <p className="mt-1 text-xs text-ink-subtle">Versi {campaign.latest_version}{campaign.confirmed ? "" : " · belum dikonfirmasi"}</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      <SystemStatusBar />

      <section className="space-y-4" aria-labelledby="library-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-brand-soft" aria-hidden />
              <h2 id="library-heading" className="text-lg font-semibold text-ink">Proyek terbaru</h2>
            </div>
            <p className="mt-1 text-sm text-ink-muted">{filteredJobs.length} dari {jobs?.length || 0} proyek</p>
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter proyek">
            {JOB_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                aria-pressed={filter === item.value}
                onClick={() => setFilter(item.value)}
                className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-150 ${filter === item.value ? "border-brand bg-brand/15 text-brand-soft" : "border-line-strong bg-surface text-ink-muted hover:border-brand/60 hover:text-ink"}`}
              >
                {item.label}<span className="tabular-nums text-ink-subtle">{counts[item.value]}</span>
              </button>
            ))}
          </div>
        </div>
        {error && <div role="alert" className="flex items-center gap-2 cg-alert"><AlertCircle className="h-4 w-4" />{error instanceof Error ? error.message : "Gagal memuat proyek"}</div>}
        {isLoading && <JobRowSkeleton />}
        {!isLoading && !error && (!jobs || jobs.length === 0) && (
          <div className="clipgen-panel rounded-panel px-4 py-14 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/15 text-brand-soft"><Plus className="h-5 w-5" /></div>
            <p className="mt-4 font-semibold text-ink">Belum ada proyek</p>
            <p className="mt-1 text-sm text-ink-muted">Pilih file atau link YouTube di atas untuk memulai.</p>
          </div>
        )}
        {!isLoading && !error && jobs && jobs.length > 0 && filteredJobs.length === 0 && (
          <div className="clipgen-panel flex items-center justify-center gap-2 rounded-panel px-4 py-10 text-sm text-ink-muted"><Search className="h-4 w-4" />Tidak ada proyek untuk filter ini</div>
        )}
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{filteredJobs.map((job) => <ProjectCard key={job.id} job={job} campaignName={job.campaign_id ? campaignNames.get(job.campaign_id) ?? "Campaign" : null} />)}</div>
      </section>
    </div>
  );
}

const STAT_TONES = {
  accent: "text-accent",
  good: "text-emerald-600 dark:text-emerald-300",
  bad: "text-rose-600 dark:text-rose-300",
  brand: "text-brand-soft",
  muted: "text-ink",
} as const;

function StatTile({ label, value, tone, href }: { label: string; value: number; tone: keyof typeof STAT_TONES; href?: string }) {
  const body = (
    <>
      <p className="text-xs font-medium text-ink-muted">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${STAT_TONES[tone]}`}>{value}</p>
    </>
  );
  const className = "clipgen-panel rounded-panel px-4 py-3";
  return href
    ? <Link href={href} className={`${className} transition-colors duration-150 hover:border-brand/60`}>{body}</Link>
    : <div className={className}>{body}</div>;
}

function ProjectCard({ job, campaignName }: { job: JobResponse; campaignName: string | null }) {
  const title = job.source_name && !job.source_name.startsWith("http") ? job.source_name : job.source_type === "youtube_url" ? "YouTube project" : "Uploaded video";
  // Failed and cancelled projects drop the violet-to-cyan gradient so progress never reads as healthy.
  const barColor = job.status === "failed" ? "rgb(244 63 94)" : job.status === "cancelled" ? "rgb(148 163 184)" : null;
  return (
    <Link href={`/jobs/${job.id}`} className="clipgen-panel group rounded-panel p-4 transition-colors duration-150 hover:border-brand/60">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-elevated text-ink-muted"><FolderOpen className="h-5 w-5" aria-hidden /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-semibold text-ink">{title}</span>
            <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${JOB_STATUS_TONES[job.status]}`}>{JOB_STATUS_LABELS[job.status]}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-subtle">
            <Clock3 className="h-3.5 w-3.5" aria-hidden />{formatDateTime(job.created_at)}<span>· Job {job.id.slice(0, 8)}</span>
          </div>
          {campaignName && (
            <p className="mt-2 inline-flex max-w-full items-center gap-1.5 rounded-full bg-brand/15 px-2 py-0.5 text-xs font-medium text-brand-soft">
              <BriefcaseBusiness className="h-3 w-3 shrink-0" aria-hidden /><span className="truncate">{campaignName}</span>
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm font-medium tabular-nums text-ink-muted"><span>{job.progress}%</span><ArrowRight className="h-4 w-4 transition-colors group-hover:text-brand-soft" aria-hidden /></div>
      </div>
      {job.error_message && <p className="mt-3 line-clamp-2 rounded-lg bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700 dark:bg-rose-400/10 dark:text-rose-200">{job.error_message}</p>}
      <div className="cg-progress mt-4" role="progressbar" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100} aria-label="Progres proyek">
        <span style={{ width: `${job.progress}%`, ...(barColor ? { background: barColor } : {}) }} />
      </div>
    </Link>
  );
}

function JobRowSkeleton() { return <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{[0, 1, 2].map((item) => <div key={item} className="clipgen-panel rounded-panel p-4"><div className="h-4 w-48 animate-pulse rounded bg-elevated" /><div className="mt-3 h-3 w-28 animate-pulse rounded bg-elevated" /><div className="mt-5 h-1.5 animate-pulse rounded bg-elevated" /></div>)}</div>; }
