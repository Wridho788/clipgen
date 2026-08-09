"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  Captions,
  Crop,
  FileVideo,
  Languages,
  Link as LinkIcon,
  Loader2,
  Scissors,
  SlidersHorizontal,
  Sparkles,
  Tags,
  UploadCloud,
  Wand2,
  Zap,
} from "lucide-react";
import { api, UploadProgress } from "@/lib/api";
import { JobProcessingOptions, ProcessingEstimateResponse } from "@/types/api";
import { formatFileSize, formatTimeEstimate } from "@/lib/status";

const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024;
const VIDEO_FILE_NAME = /\.(mp4|mkv|avi|mov|webm|m4v)$/i;

type YoutubeProcessingMode = "automatic" | "manual";
type ManualYoutubeOptions = Pick<
  JobProcessingOptions,
  "crop_vertical" | "generate_highlights" | "generate_metadata" | "generate_subtitles"
>;

const DEFAULT_MANUAL_YOUTUBE_OPTIONS: ManualYoutubeOptions = {
  crop_vertical: false,
  generate_highlights: true,
  generate_metadata: true,
  generate_subtitles: true,
};

export function VideoUpload() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadStartedAtRef = useRef<number | null>(null);
  const [mode, setMode] = useState<"file" | "youtube">("file");
  const [metadataLanguage, setMetadataLanguage] = useState<"id" | "en">("id");
  const [youtubeProcessingMode, setYoutubeProcessingMode] = useState<YoutubeProcessingMode>("automatic");
  const [manualYoutubeOptions, setManualYoutubeOptions] = useState<ManualYoutubeOptions>(
    DEFAULT_MANUAL_YOUTUBE_OPTIONS
  );
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploadEtaSeconds, setUploadEtaSeconds] = useState<number | null>(null);
  const [processingEstimate, setProcessingEstimate] = useState<ProcessingEstimateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileProcessingOptions = {
    metadata_language: metadataLanguage,
    processing_mode: "manual",
    crop_vertical: false,
    generate_highlights: true,
    generate_metadata: true,
    generate_subtitles: false,
  } satisfies Partial<JobProcessingOptions>;

  const youtubeProcessingOptions = {
    metadata_language: metadataLanguage,
    processing_mode: youtubeProcessingMode,
    ...(youtubeProcessingMode === "automatic"
      ? {
          crop_vertical: false,
          generate_highlights: true,
          generate_metadata: true,
          generate_subtitles: false,
        }
      : manualYoutubeOptions),
  } satisfies Partial<JobProcessingOptions>;

  const submitFile = async (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("video/") && !VIDEO_FILE_NAME.test(file.name)) {
      setError("File harus berupa video.");
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError("File melebihi batas 2GB.");
      return;
    }

    setSelectedFile(file);
    setUploading(true);
    setUploadProgress(null);
    setUploadEtaSeconds(null);
    setProcessingEstimate(null);
    setError(null);

    try {
      const durationSeconds = await getVideoDuration(file);
      if (durationSeconds) {
        try {
          const estimate = await api.getProcessingEstimate(durationSeconds, "upload", fileProcessingOptions);
          setProcessingEstimate(estimate);
        } catch {
          // Estimation must not block a valid upload when the API is temporarily unavailable.
        }
      }

      uploadStartedAtRef.current = performance.now();
      const result = await api.uploadVideo(file, fileProcessingOptions, (progress) => {
        setUploadProgress(progress);
        const elapsedSeconds = Math.max(0.1, (performance.now() - (uploadStartedAtRef.current || performance.now())) / 1000);
        const bytesPerSecond = progress.loaded / elapsedSeconds;
        setUploadEtaSeconds(
          bytesPerSecond > 0 ? Math.max(0, (progress.total - progress.loaded) / bytesPerSecond) : null,
        );
      });
      router.push(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload gagal");
      setUploading(false);
    }
  };

  const handleFileSelect = async (event: ChangeEvent<HTMLInputElement>) => {
    await submitFile(event.target.files?.[0] || null);
    event.target.value = "";
  };

  const handleDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    await submitFile(event.dataTransfer.files?.[0] || null);
  };

  const handleYoutubeSubmit = async () => {
    const trimmedUrl = youtubeUrl.trim();
    if (!trimmedUrl) return;
    if (!/^https?:\/\/(?:[a-z0-9-]+\.)?(youtube\.com|youtu\.be)\//i.test(trimmedUrl)) {
      setError("URL YouTube tidak valid.");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const result = await api.youtubeUrl(trimmedUrl, youtubeProcessingOptions);
      router.push(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job YouTube gagal dibuat");
      setUploading(false);
    }
  };

  const toggleManualOption = (key: keyof ManualYoutubeOptions) => {
    setManualYoutubeOptions((current) => ({
      ...current,
      [key]: !current[key],
    }));
  };

  return (
    <section className="clipgen-panel overflow-hidden">
      <div className="border-b border-slate-200 bg-slate-950 px-4 py-4 text-white dark:border-slate-800 dark:bg-black/30 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center border border-cyan-300/50 bg-cyan-300/10 text-cyan-200">
              <Scissors className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold">Studio klip</h2>
              <p className="text-xs text-slate-300">Upload asset atau proses link YouTube.</p>
            </div>
          </div>

          <div className="inline-flex w-fit border border-white/10 bg-white/5 p-1">
            <SourceModeButton
              active={mode === "file"}
              disabled={uploading}
              icon={<FileVideo className="h-4 w-4" />}
              label="File"
              onClick={() => setMode("file")}
            />
            <SourceModeButton
              active={mode === "youtube"}
              disabled={uploading}
              icon={<LinkIcon className="h-4 w-4" />}
              label="YouTube"
              onClick={() => setMode("youtube")}
            />
          </div>
        </div>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex items-center border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-900/70">
            <Languages className="mx-2 h-4 w-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />
            <OptionButton
              active={metadataLanguage === "id"}
              disabled={uploading}
              label="Indonesia"
              onClick={() => setMetadataLanguage("id")}
              title="Metadata Bahasa Indonesia"
            />
            <OptionButton
              active={metadataLanguage === "en"}
              disabled={uploading}
              label="English"
              onClick={() => setMetadataLanguage("en")}
              title="Metadata English"
            />
          </div>
          {mode === "youtube" && (
            <div className="inline-flex items-center border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-900/70">
              <Wand2 className="mx-2 h-4 w-4 text-cyan-600 dark:text-cyan-300" aria-hidden="true" />
              <OptionButton
                active={youtubeProcessingMode === "automatic"}
                disabled={uploading}
                label="Otomatis"
                onClick={() => setYoutubeProcessingMode("automatic")}
                title="Mode otomatis"
              />
              <OptionButton
                active={youtubeProcessingMode === "manual"}
                disabled={uploading}
                label="Manual"
                onClick={() => setYoutubeProcessingMode("manual")}
                title="Mode manual"
              />
            </div>
          )}
        </div>

        {mode === "file" ? (
          <div
            onDragEnter={() => setDragActive(true)}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            className={`flex min-h-48 flex-col items-center justify-center border border-dashed p-5 text-center transition ${
              dragActive
                ? "border-cyan-500 bg-cyan-50 dark:border-cyan-300 dark:bg-cyan-300/10"
                : "border-slate-300 bg-white dark:border-slate-800 dark:bg-slate-950/40"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleFileSelect}
              disabled={uploading}
              className="hidden"
              id="file-input"
            />
            <UploadCloud className="mb-3 h-9 w-9 text-cyan-600 dark:text-cyan-300" />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-cyan-300 dark:text-slate-950 dark:hover:bg-cyan-200"
            >
              {uploading && <Loader2 className="h-4 w-4 animate-spin" />}
              {uploading ? "Mengupload" : "Pilih video"}
            </button>
            {selectedFile && (
              <p className="mt-3 break-all text-sm text-slate-600 dark:text-slate-300">
                {selectedFile.name} - {formatFileSize(selectedFile.size)}
              </p>
            )}
            {uploading && (
              <div className="mt-3 w-full max-w-md text-left">
                <div className="h-2 overflow-hidden bg-slate-100 dark:bg-slate-800" role="progressbar" aria-valuenow={uploadProgress?.percent || 0}>
                  <div className="h-full bg-cyan-400 transition-all duration-300" style={{ width: `${uploadProgress?.percent || 0}%` }} />
                </div>
                <p className="mt-2 text-center text-xs text-slate-600 dark:text-slate-300">
                  {uploadProgress
                    ? `Upload ${uploadProgress.percent}%${uploadEtaSeconds !== null ? ` - sisa ${formatTimeEstimate(uploadEtaSeconds)}` : ""}`
                    : "Menyiapkan upload dan estimasi proses..."}
                </p>
              </div>
            )}
            {processingEstimate && (
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                Estimasi pemrosesan setelah upload: {formatTimeEstimate(processingEstimate.estimated_processing_seconds)}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center border border-slate-300 bg-white focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-950/70 dark:focus-within:border-cyan-300">
              <LinkIcon className="ml-3 h-4 w-4 text-slate-500 dark:text-slate-400" />
              <input
                type="url"
                value={youtubeUrl}
                onChange={(event) => setYoutubeUrl(event.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                disabled={uploading}
                className="w-full bg-transparent px-3 py-2.5 text-sm text-slate-950 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed dark:text-slate-50 dark:placeholder:text-slate-500"
              />
            </div>

            {youtubeProcessingMode === "automatic" ? (
              <div className="grid gap-2 sm:grid-cols-4">
                <ModePill icon={<Zap className="h-4 w-4" />} label="Landscape" active />
                <ModePill icon={<Scissors className="h-4 w-4" />} label="Lewati intro" active />
                <ModePill icon={<Sparkles className="h-4 w-4" />} label="Multi-klip" active />
                <ModePill icon={<Tags className="h-4 w-4" />} label="Metadata on" active />
              </div>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                <ToggleTile
                  icon={<Crop className="h-4 w-4" />}
                  label="Crop vertical"
                  active={manualYoutubeOptions.crop_vertical}
                  onClick={() => toggleManualOption("crop_vertical")}
                  disabled={uploading}
                />
                <ToggleTile
                  icon={<Sparkles className="h-4 w-4" />}
                  label="Generate highlight"
                  active={manualYoutubeOptions.generate_highlights}
                  onClick={() => toggleManualOption("generate_highlights")}
                  disabled={uploading}
                />
                <ToggleTile
                  icon={<Tags className="h-4 w-4" />}
                  label="Generate metadata"
                  active={manualYoutubeOptions.generate_metadata}
                  onClick={() => toggleManualOption("generate_metadata")}
                  disabled={uploading}
                />
                <ToggleTile
                  icon={<Captions className="h-4 w-4" />}
                  label="Generate subtitle"
                  active={manualYoutubeOptions.generate_subtitles}
                  onClick={() => toggleManualOption("generate_subtitles")}
                  disabled={uploading}
                />
              </div>
            )}

            <button
              onClick={handleYoutubeSubmit}
              disabled={uploading || !youtubeUrl.trim()}
              className="inline-flex w-full items-center justify-center gap-2 bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-cyan-300 dark:text-slate-950 dark:hover:bg-cyan-200"
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SlidersHorizontal className="h-4 w-4" />}
              {uploading ? "Membuat job" : "Proses"}
            </button>
          </div>
        )}

        {error && <p className="border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-400/30 dark:bg-rose-400/10 dark:text-rose-200">{error}</p>}
      </div>
    </section>
  );
}

function SourceModeButton({
  active,
  disabled,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  disabled: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
        active ? "bg-cyan-300 text-slate-950" : "text-slate-300 hover:bg-white/10 hover:text-white"
      }`}
      title={label}
    >
      {icon}
      {label}
    </button>
  );
}

function OptionButton({
  active,
  disabled,
  label,
  onClick,
  title,
}: {
  active: boolean;
  disabled: boolean;
  label: string;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`px-2.5 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
        active
          ? "bg-slate-950 text-white dark:bg-cyan-300 dark:text-slate-950"
          : "text-slate-600 hover:bg-white dark:text-slate-300 dark:hover:bg-slate-800"
      }`}
    >
      {label}
    </button>
  );
}

function ToggleTile({
  active,
  disabled,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  disabled: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-h-14 items-center justify-between gap-3 border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${
        active
          ? "border-cyan-500 bg-cyan-50 text-slate-950 dark:border-cyan-300 dark:bg-cyan-300/10 dark:text-cyan-100"
          : "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400"
      }`}
      title={label}
    >
      <span className="inline-flex items-center gap-2">
        {icon}
        {label}
      </span>
      <span className={`h-2.5 w-2.5 ${active ? "bg-cyan-500 dark:bg-cyan-300" : "bg-slate-300 dark:bg-slate-700"}`} />
    </button>
  );
}

function ModePill({ active = false, icon, label }: { active?: boolean; icon: ReactNode; label: string }) {
  return (
    <div
      className={`flex min-h-11 items-center gap-2 border px-3 py-2 text-sm ${
        active
          ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-200"
          : "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400"
      }`}
    >
      {icon}
      {label}
    </div>
  );
}

function getVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    const objectUrl = URL.createObjectURL(file);
    const cleanup = () => {
      URL.revokeObjectURL(objectUrl);
      video.removeAttribute("src");
      video.load();
    };
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : null;
      cleanup();
      resolve(duration);
    };
    video.onerror = () => {
      cleanup();
      resolve(null);
    };
    video.src = objectUrl;
  });
}
