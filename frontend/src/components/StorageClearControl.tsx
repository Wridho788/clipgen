"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArchiveRestore, CheckCircle2, Loader2, Trash2, X } from "lucide-react";

import { api } from "@/lib/api";
import { formatFileSize } from "@/lib/status";
import { StorageClearMode, StorageClearResponse } from "@/types/api";

/** A global control: reset belongs to the dashboard, never to an individual job. */
export function StorageClearControl() {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<StorageClearMode>("permanent");
  const [confirmation, setConfirmation] = useState("");
  const [result, setResult] = useState<StorageClearResponse | null>(null);
  const clearStorage = useMutation({
    mutationFn: (nextMode: StorageClearMode) => api.clearStorage(nextMode),
    onSuccess: (response) => {
      setResult(response);
      setIsOpen(false);
      setConfirmation("");
      queryClient.invalidateQueries({ queryKey: ["system-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["clips"] });
    },
  });

  const confirmClear = () => {
    if (clearStorage.isPending || (mode === "permanent" && confirmation !== "HAPUS SEMUA")) return;
    clearStorage.mutate(mode);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 transition hover:border-rose-400 hover:bg-rose-100 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-200 dark:hover:bg-rose-400/20"
      >
        <Trash2 className="h-4 w-4" />
        Reset workspace
      </button>

      {result && (
        <div role="status" className="fixed bottom-4 right-4 z-50 flex max-w-sm items-start gap-2 rounded-xl border border-emerald-200 bg-white p-3 text-xs text-emerald-800 shadow-xl dark:border-emerald-400/30 dark:bg-slate-900 dark:text-emerald-100">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            {result.jobs_deleted} job, {result.clips_deleted} klip, dan {result.files_handled} file {result.mode === "permanent" ? `dihapus; ${formatFileSize(result.bytes_reclaimed)} dibebaskan.` : "dipindahkan ke Recycle Bin ClipGen."}
          </p>
          <button type="button" onClick={() => setResult(null)} className="text-emerald-700 dark:text-emerald-200" aria-label="Tutup notifikasi"><X className="h-4 w-4" /></button>
        </div>
      )}

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-end bg-slate-950/55 p-4 backdrop-blur-sm sm:items-center sm:justify-center" role="presentation">
          <section role="dialog" aria-modal="true" aria-labelledby="reset-workspace-title" className="w-full max-w-lg rounded-2xl border border-rose-200 bg-white p-5 shadow-2xl dark:border-rose-400/30 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-4">
              <div className="flex gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-700 dark:bg-rose-400/15 dark:text-rose-200"><AlertTriangle className="h-5 w-5" /></div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-rose-600 dark:text-rose-300">Aksi global</p>
                  <h2 id="reset-workspace-title" className="mt-1 text-lg font-semibold text-slate-950 dark:text-slate-50">Reset workspace</h2>
                </div>
              </div>
              <button type="button" onClick={() => setIsOpen(false)} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-100" aria-label="Tutup"><X className="h-5 w-5" /></button>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">
              Menghapus seluruh job, hasil klip, video sumber, file sementara, feedback, dan riwayat untuk workspace ini. Akun serta konfigurasi ClipGen tidak ikut dihapus. Job aktif atau menunggu akan memblokir aksi ini.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <button type="button" onClick={() => setMode("recycle")} className={`rounded-xl border p-3 text-left transition ${mode === "recycle" ? "border-violet-400 bg-violet-50 ring-1 ring-violet-200 dark:border-violet-300 dark:bg-violet-400/10" : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600"}`}>
                <span className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100"><ArchiveRestore className="h-4 w-4" />Ke Recycle Bin</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500 dark:text-slate-400">Riwayat dihapus, file dipindahkan dan ruang disk belum dibebaskan.</span>
              </button>
              <button type="button" onClick={() => setMode("permanent")} className={`rounded-xl border p-3 text-left transition ${mode === "permanent" ? "border-rose-400 bg-rose-50 ring-1 ring-rose-200 dark:border-rose-300 dark:bg-rose-400/10" : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600"}`}>
                <span className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100"><Trash2 className="h-4 w-4" />Hapus permanen</span>
                <span className="mt-1 block text-xs leading-5 text-slate-500 dark:text-slate-400">Menghapus file, riwayat, dan isi Recycle Bin secara permanen.</span>
              </button>
            </div>
            {mode === "permanent" && (
              <label className="mt-4 block text-sm font-medium text-slate-700 dark:text-slate-200">
                Ketik <strong>HAPUS SEMUA</strong> untuk melanjutkan
                <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-rose-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-50" />
              </label>
            )}
            {clearStorage.error && <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-100">{clearStorage.error instanceof Error ? clearStorage.error.message : "Gagal mereset workspace"}</p>}
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={() => setIsOpen(false)} disabled={clearStorage.isPending} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">Batal</button>
              <button type="button" onClick={confirmClear} disabled={clearStorage.isPending || (mode === "permanent" && confirmation !== "HAPUS SEMUA")} className="inline-flex items-center gap-2 rounded-lg bg-rose-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">
                {clearStorage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} {mode === "permanent" ? "Hapus semua data & job" : "Pindahkan ke Recycle Bin"}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
