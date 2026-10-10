"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AlertCircle, ArrowRight, Clock3, FolderOpen, Plus, RefreshCw, Search, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime, isActiveJobStatus, isTerminalJobStatus, JOB_STATUS_LABELS, JOB_STATUS_TONES } from "@/lib/status";
import { JobResponse, JobStatus } from "@/types/api";
import { VideoUpload } from "@/components/VideoUpload";
import { SystemStatusBar } from "@/components/SystemStatusBar";
import { StorageClearControl } from "@/components/StorageClearControl";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AccountControl } from "@/components/AuthGate";

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
      <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-sm font-bold tracking-tight text-white shadow-lg shadow-slate-950/15 dark:bg-violet-300 dark:text-slate-950">CG</div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-600 dark:text-violet-300">Creator workspace</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950 dark:text-slate-50 sm:text-4xl">Bikin klip yang siap publish.</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500 dark:text-slate-400">Ubah video panjang menjadi klip short-form dan metadata yang siap ditinjau.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2"><ThemeToggle /><AccountControl /><StorageClearControl /><button type="button" onClick={() => refetch()} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-violet-300" title="Refresh projects"><RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />Refresh</button></div>
      </header>

      <section className="grid gap-4 rounded-3xl bg-slate-950 p-6 text-white shadow-xl shadow-slate-950/10 dark:bg-violet-300 dark:text-slate-950 sm:grid-cols-[1fr_auto] sm:items-center sm:p-8">
        <div><div className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 dark:bg-slate-950/10 dark:text-slate-800"><Sparkles className="h-3.5 w-3.5" />Workflow short-form</div><h2 className="max-w-xl text-2xl font-semibold tracking-tight sm:text-3xl">Satu proyek, dari source sampai konten siap tayang.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-slate-300 dark:text-slate-800">Pilih campaign brief jika kamu sedang mengerjakan guideline brand tertentu. ClipGen akan membawa aturan itu sampai ke metadata dan checklist distribusi.</p></div>
        <div className="hidden rounded-2xl bg-white/10 p-4 text-sm text-slate-200 sm:block dark:bg-slate-950/10 dark:text-slate-800"><p className="font-semibold">3 langkah sederhana</p><p className="mt-2">1. Pilih video</p><p>2. Pilih campaign</p><p>3. Review & publish</p></div>
      </section>

      <SystemStatusBar /><VideoUpload />

      <section className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><div className="flex items-center gap-2 text-violet-600 dark:text-violet-300"><FolderOpen className="h-4 w-4" /><p className="text-xs font-semibold uppercase tracking-[0.18em]">Library</p></div><h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950 dark:text-slate-50">Proyek terbaru</h2><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{filteredJobs.length} dari {jobs?.length || 0} proyek</p></div><div className="flex flex-wrap gap-2">{JOB_FILTERS.map((item) => <button key={item.value} type="button" onClick={() => setFilter(item.value)} className={`inline-flex min-h-9 items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition ${filter === item.value ? "border-slate-950 bg-slate-950 text-white dark:border-violet-300 dark:bg-violet-300 dark:text-slate-950" : "border-slate-200 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-violet-300"}`}>{item.label}<span className={filter === item.value ? "text-slate-300 dark:text-slate-700" : "text-slate-400"}>{counts[item.value]}</span></button>)}</div></div>
        {error && <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-200"><AlertCircle className="h-4 w-4" />{error instanceof Error ? error.message : "Gagal memuat proyek"}</div>}
        {isLoading && <JobRowSkeleton />}
        {!isLoading && !error && (!jobs || jobs.length === 0) && <div className="clipgen-panel rounded-2xl px-4 py-12 text-center"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200"><Plus className="h-5 w-5" /></div><p className="mt-4 font-semibold text-slate-900 dark:text-slate-100">Belum ada proyek</p><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Pilih file atau link YouTube di atas untuk memulai.</p></div>}
        {!isLoading && !error && jobs && jobs.length > 0 && filteredJobs.length === 0 && <div className="clipgen-panel flex items-center justify-center gap-2 rounded-2xl px-4 py-10 text-sm text-slate-500 dark:text-slate-400"><Search className="h-4 w-4" />Tidak ada proyek untuk filter ini</div>}
        <div className="grid gap-3 lg:grid-cols-2">{filteredJobs.map((job) => <ProjectCard key={job.id} job={job} />)}</div>
      </section>

    </div>
  );
}

function ProjectCard({ job }: { job: JobResponse }) {
  const title = job.source_name && !job.source_name.startsWith("http") ? job.source_name : job.source_type === "youtube_url" ? "YouTube project" : "Uploaded video";
  const progressTone = job.status === "failed" ? "bg-rose-500" : job.status === "done" ? "bg-emerald-500" : job.status === "cancelled" ? "bg-slate-400" : "bg-violet-500";
  return <Link href={`/jobs/${job.id}`} className="clipgen-panel group rounded-2xl p-4 transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-lg hover:shadow-violet-900/5 dark:hover:border-violet-300/60"><div className="flex items-start gap-3"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300"><FolderOpen className="h-5 w-5" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="truncate font-semibold text-slate-950 dark:text-slate-50">{title}</span><span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${JOB_STATUS_TONES[job.status]}`}>{JOB_STATUS_LABELS[job.status]}</span></div><div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400"><Clock3 className="h-3.5 w-3.5" />{formatDateTime(job.created_at)}<span>· Job {job.id.slice(0, 8)}</span></div></div><div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-300"><span>{job.progress}%</span><ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:text-violet-600" /></div></div>{job.error_message && <p className="mt-3 line-clamp-2 rounded-lg bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700 dark:bg-rose-400/10 dark:text-rose-200">{job.error_message}</p>}<div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className={`h-full rounded-full transition-all ${progressTone}`} style={{ width: `${job.progress}%` }} /></div></Link>;
}

function JobRowSkeleton() { return <div className="grid gap-3 lg:grid-cols-2">{[0, 1].map((item) => <div key={item} className="clipgen-panel rounded-2xl p-4"><div className="h-4 w-48 animate-pulse rounded bg-slate-200 dark:bg-slate-800" /><div className="mt-3 h-3 w-28 animate-pulse rounded bg-slate-100 dark:bg-slate-900" /><div className="mt-5 h-1.5 animate-pulse rounded bg-slate-100 dark:bg-slate-900" /></div>)}</div>; }
