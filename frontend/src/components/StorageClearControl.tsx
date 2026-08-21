"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArchiveRestore, AlertTriangle, Loader2, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { formatFileSize } from "@/lib/status";
import { StorageClearMode, StorageClearResponse } from "@/types/api";

export function StorageClearControl() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<StorageClearResponse | null>(null);
  const clearStorage = useMutation({
    mutationFn: (mode: StorageClearMode) => api.clearStorage(mode),
    onSuccess: (response) => {
      setResult(response);
      queryClient.invalidateQueries({ queryKey: ["system-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["clips"] });
    },
  });

  const requestClear = (mode: StorageClearMode) => {
    if (clearStorage.isPending) return;
    if (mode === "recycle") {
      const accepted = window.confirm(
        "Pindahkan semua video, clip, file sementara, dan riwayat job ke Recycle Bin ClipGen? " +
        "Job aktif atau menunggu akan memblokir tindakan ini. Mode ini dapat dipulihkan secara manual, " +
        "tetapi belum membebaskan ruang disk.",
      );
      if (!accepted) return;
    } else {
      const confirmation = window.prompt(
        "Tindakan ini menghapus permanen video, clip, riwayat job, dan isi Recycle Bin ClipGen. " +
        "Ketik HAPUS PERMANEN untuk melanjutkan.",
      );
      if (confirmation !== "HAPUS PERMANEN") return;
    }
    setResult(null);
    clearStorage.mutate(mode);
  };

  return (
    <section className="border border-amber-200 bg-amber-50/70 p-4 dark:border-amber-400/30 dark:bg-amber-400/10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-900 dark:text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            Bersihkan storage
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-amber-800 dark:text-amber-100">
            Menghapus source video, hasil clip, file sementara, serta riwayat job. Recycle Bin ClipGen menyimpan file
            dan snapshot database di dalam project; hapus permanen mengosongkan semuanya termasuk recycle bin.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => requestClear("recycle")}
            disabled={clearStorage.isPending}
            className="inline-flex items-center gap-2 border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-900 disabled:cursor-not-allowed disabled:opacity-60 dark:border-amber-300/40 dark:bg-slate-950 dark:text-amber-100"
          >
            {clearStorage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArchiveRestore className="h-4 w-4" />}
            Ke Recycle Bin
          </button>
          <button
            type="button"
            onClick={() => requestClear("permanent")}
            disabled={clearStorage.isPending}
            className="inline-flex items-center gap-2 bg-rose-700 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {clearStorage.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Hapus permanen
          </button>
        </div>
      </div>
      {clearStorage.error && (
        <p className="mt-3 border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-100">
          {clearStorage.error instanceof Error ? clearStorage.error.message : "Gagal membersihkan storage"}
        </p>
      )}
      {result && (
        <p className="mt-3 border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-100">
          {result.mode === "recycle"
            ? `${result.files_handled} file (${formatFileSize(result.bytes_moved)}) dipindahkan ke Recycle Bin ClipGen. Ruang disk belum dibebaskan.`
            : `${result.files_handled} file dihapus permanen dan ${formatFileSize(result.bytes_reclaimed)} dibebaskan.`}
          {` ${result.jobs_deleted} job dan ${result.clips_deleted} clip dihapus dari riwayat.`}
        </p>
      )}
    </section>
  );
}
