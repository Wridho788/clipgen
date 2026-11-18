"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  Check,
  AlertTriangle,
  FileVideo,
  Languages,
  Link as LinkIcon,
  Loader2,
  RefreshCw,
  Scissors,
  SlidersHorizontal,
  Tags,
  UploadCloud,
  Wand2,
} from "lucide-react";
import { api, UploadProgress } from "@/lib/api";
import { CampaignBrief, CampaignDetail, JobProcessingOptions, ProcessingEstimateResponse, YoutubePreflightResponse } from "@/types/api";
import { formatFileSize, formatTimeEstimate } from "@/lib/status";

const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024;
const VIDEO_FILE_NAME = /\.(mp4|mkv|avi|mov|webm|m4v)$/i;

type YoutubeProcessingMode = "automatic" | "manual";
type ManualYoutubeOptions = Pick<JobProcessingOptions, "generate_metadata">;
type RenderOptions = Pick<
  JobProcessingOptions,
  "output_preset" | "visual_style"
>;

const DEFAULT_MANUAL_YOUTUBE_OPTIONS: ManualYoutubeOptions = {
  generate_metadata: true,
};

const DEFAULT_RENDER_OPTIONS: RenderOptions = {
  output_preset: "tiktok",
  visual_style: "blur",
};

export function VideoUpload() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadStartedAtRef = useRef<number | null>(null);
  const [mode, setMode] = useState<"file" | "youtube">("file");
  const [metadataLanguage, setMetadataLanguage] = useState<"id" | "en">("id");
  // Spoken language sent to Whisper. Auto-detection mislabelled an Indonesian
  // TV show (music intro) as Catalan, so Indonesian is the explicit default.
  const [audioLanguage, setAudioLanguage] = useState<"auto" | "id" | "en">("id");
  const [youtubeProcessingMode, setYoutubeProcessingMode] = useState<YoutubeProcessingMode>("automatic");
  const [manualYoutubeOptions, setManualYoutubeOptions] = useState<ManualYoutubeOptions>(
    DEFAULT_MANUAL_YOUTUBE_OPTIONS
  );
  const [renderOptions, setRenderOptions] = useState<RenderOptions>(DEFAULT_RENDER_OPTIONS);
  // Editable transcript captions burned into exports (file + manual YouTube).
  const [burnCaptions, setBurnCaptions] = useState(true);
  // Saved campaign chosen for this video. The detail is loaded on selection so the
  // job pins exactly the version whose rules are shown here.
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [campaignLoadingId, setCampaignLoadingId] = useState<string | null>(null);
  const [campaignError, setCampaignError] = useState<string | null>(null);
  const { data: savedCampaigns, isLoading: campaignsLoading } = useQuery({
    queryKey: ["campaigns", { showArchived: false }],
    queryFn: () => api.listCampaigns(false),
  });
  const campaignBrief: CampaignBrief | null = campaign
    ? {
        ...campaign.configuration.config.rules,
        platforms: campaign.configuration.config.platforms.length > 0
          ? campaign.configuration.config.platforms
          : campaign.configuration.config.rules.platforms,
      }
    : null;
  const selectCampaign = async (campaignId: string | null) => {
    setCampaignError(null);
    if (!campaignId) {
      setCampaign(null);
      return;
    }
    setCampaignLoadingId(campaignId);
    try {
      setCampaign(await api.getCampaign(campaignId));
    } catch (loadError) {
      setCampaignError(loadError instanceof Error ? loadError.message : "Gagal memuat campaign.");
    } finally {
      setCampaignLoadingId(null);
    }
  };
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubePreflight, setYoutubePreflight] = useState<YoutubePreflightResponse | null>(null);
  const [checkingYoutubePreflight, setCheckingYoutubePreflight] = useState(false);
  const [youtubePreflightError, setYoutubePreflightError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploadEtaSeconds, setUploadEtaSeconds] = useState<number | null>(null);
  const [processingEstimate, setProcessingEstimate] = useState<ProcessingEstimateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileProcessingOptions = {
    min_clip_seconds: campaignBrief?.min_clip_seconds ?? 10,
    max_clip_seconds: campaignBrief?.max_clip_seconds ?? 60,
    clip_count: 0,
    metadata_language: metadataLanguage,
    transcript_language: audioLanguage,
    processing_mode: "manual",
    crop_vertical: false,
    generate_metadata: true,
    burn_captions: burnCaptions,
    ...renderOptions,
    campaign_id: campaign?.id ?? null,
    campaign_configuration_version: campaign?.latest_version ?? null,
  } satisfies Partial<JobProcessingOptions>;

  const youtubeProcessingOptions = {
    min_clip_seconds: campaignBrief?.min_clip_seconds ?? 10,
    max_clip_seconds: campaignBrief?.max_clip_seconds ?? 60,
    clip_count: 0,
    metadata_language: metadataLanguage,
    transcript_language: audioLanguage,
    processing_mode: youtubeProcessingMode,
    crop_vertical: false,
    ...renderOptions,
    campaign_id: campaign?.id ?? null,
    campaign_configuration_version: campaign?.latest_version ?? null,
    ...(youtubeProcessingMode === "automatic"
      ? {
          generate_metadata: true,
        }
      : { ...manualYoutubeOptions, burn_captions: burnCaptions }),
  } satisfies Partial<JobProcessingOptions>;

  const refreshYoutubePreflight = useCallback(async () => {
    setCheckingYoutubePreflight(true);
    setYoutubePreflightError(null);
    try {
      setYoutubePreflight(await api.getYoutubePreflight());
    } catch (err) {
      setYoutubePreflight(null);
      setYoutubePreflightError(
        err instanceof Error ? err.message : "Status sesi YouTube tidak dapat diperiksa.",
      );
    } finally {
      setCheckingYoutubePreflight(false);
    }
  }, []);

  useEffect(() => {
    if (mode === "youtube") void refreshYoutubePreflight();
  }, [mode, refreshYoutubePreflight]);

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

    // The estimate is informational only: run it alongside the upload so a slow or
    // busy API never delays the transfer itself.
    void getVideoDuration(file)
      .then((durationSeconds) => (
        durationSeconds ? api.getProcessingEstimate(durationSeconds, "upload", fileProcessingOptions) : null
      ))
      .then((estimate) => {
        if (estimate) setProcessingEstimate(estimate);
      })
      .catch(() => {
        // Estimation must not block a valid upload when the API is temporarily unavailable.
      });

    try {
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
    if (youtubePreflight && !youtubePreflight.can_start) {
      setError(youtubePreflight.message);
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
    <section className="clipgen-panel overflow-hidden rounded-3xl">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-4 text-slate-950 dark:border-slate-800 dark:bg-slate-900/70 dark:text-white sm:px-6 sm:py-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200">
              <Scissors className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold">Studio klip</h2>
              <p className="text-xs text-slate-500 dark:text-slate-300">Mulai dari video, lalu review hasilnya sebelum publish.</p>
            </div>
          </div>

          <div className="inline-flex w-fit rounded-xl border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-950">
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
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950/70 sm:p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-700 dark:bg-violet-400/15 dark:text-violet-200">
                <BriefcaseBusiness className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-950 dark:text-slate-50">Campaign brief</p>
                <p className="mt-1 max-w-xl text-xs leading-5 text-slate-500 dark:text-slate-400">
                  Pilih guideline supaya durasi, hook, CTA, hashtag, dan aturan konten ikut terjaga saat produksi.
                </p>
              </div>
            </div>
            <span className="inline-flex w-fit items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-200">
              {campaign ? `Guideline aktif · versi ${campaign.latest_version}` : "Tanpa campaign"}
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <CampaignOption
              active={!campaignBrief}
              disabled={uploading}
              title="Bebas memilih aturan campaign"
              description="Gunakan pengaturan umum ClipGen"
              onClick={() => selectCampaign(null)}
            />
            {savedCampaigns?.map((item) => (
              <CampaignOption
                key={item.id}
                active={campaign?.id === item.id}
                disabled={uploading || campaignLoadingId !== null}
                title={item.name}
                description={campaignLoadingId === item.id ? "Memuat aturan…" : `Versi ${item.latest_version}${item.confirmed ? "" : " · belum dikonfirmasi"}`}
                onClick={() => selectCampaign(item.id)}
              />
            ))}
          </div>
          {campaignsLoading && <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Memuat campaign tersimpan…</p>}
          {campaignError && <p role="alert" className="mt-3 text-xs font-medium text-rose-600 dark:text-rose-300">{campaignError}</p>}
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            Punya campaign baru?{" "}
            <Link href="/campaigns/new" className="font-medium text-violet-700 underline-offset-2 hover:underline dark:text-violet-300">Import dari teks</Link>
            {" · "}
            <Link href="/campaigns" className="font-medium text-violet-700 underline-offset-2 hover:underline dark:text-violet-300">Kelola campaign</Link>
          </p>
          {campaignBrief && (
            <div className="mt-3 space-y-2 border-t border-slate-100 pt-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-500" /> Hook {campaignBrief.hook_max_seconds} detik</span>
                {campaignBrief.cta && <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-500" /> CTA otomatis</span>}
                {campaignBrief.hashtags.length > 0 && <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-500" /> {campaignBrief.hashtags.length} hashtag wajib</span>}
                {campaignBrief.required_phrases.length > 0 && <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-500" /> Narasi wajib</span>}
                {campaignBrief.organic_only && <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-emerald-500" /> Organic-only</span>}
              </div>
              <p className="leading-5 text-slate-500 dark:text-slate-400">
                {campaignBrief.required_visuals.length > 0 && <>Visual: {campaignBrief.required_visuals.join(", ")}. </>}
                {campaignBrief.prohibited_terms.length > 0 && <>Hindari: {campaignBrief.prohibited_terms.slice(0, 5).join(", ")}.</>}
              </p>
            </div>
          )}
        </section>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-900/70">
            <Languages className="mx-2 h-4 w-4 text-slate-500 dark:text-slate-400" aria-hidden="true" />
            <OptionButton active={metadataLanguage === "id"} disabled={uploading} label="Indonesia" onClick={() => setMetadataLanguage("id")} title="Metadata Bahasa Indonesia" />
            <OptionButton active={metadataLanguage === "en"} disabled={uploading} label="English" onClick={() => setMetadataLanguage("en")} title="Metadata English" />
          </div>
          <label className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300">
            Bahasa audio
            <select
              aria-label="Bahasa audio"
              value={audioLanguage}
              disabled={uploading}
              onChange={(event) => setAudioLanguage(event.target.value as "auto" | "id" | "en")}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="id">Indonesia</option>
              <option value="en">English</option>
              <option value="auto">Deteksi otomatis</option>
            </select>
          </label>
          {mode === "youtube" && (
            <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-900/70">
              <Wand2 className="mx-2 h-4 w-4 text-violet-600 dark:text-violet-300" aria-hidden="true" />
              <OptionButton active={youtubeProcessingMode === "automatic"} disabled={uploading} label="Otomatis" onClick={() => setYoutubeProcessingMode("automatic")} title="Mode otomatis" />
              <OptionButton active={youtubeProcessingMode === "manual"} disabled={uploading} label="Manual" onClick={() => setYoutubeProcessingMode("manual")} title="Mode manual" />
            </div>
          )}
        </div>

        <section className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-800 dark:bg-slate-900/50">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Workflow short-form</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">Kandidat di batas kalimat → format sosial → caption → review &amp; edit → export.</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Format export
              <select
                value={renderOptions.output_preset}
                disabled={uploading}
                onChange={(event) => setRenderOptions((current) => ({ ...current, output_preset: event.target.value as RenderOptions["output_preset"] }))}
                className="mt-1 w-full border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 outline-none focus:border-cyan-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              >
                <option value="tiktok">TikTok · 9:16</option>
                <option value="reels">Instagram Reels · 9:16</option>
                <option value="youtube_shorts">YouTube Shorts · 9:16</option>
                <option value="square">Square post · 1:1</option>
                <option value="landscape">YouTube landscape · 16:9</option>
                <option value="original">Original aspect</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Style visual
              <select
                value={renderOptions.visual_style}
                disabled={uploading}
                onChange={(event) => setRenderOptions((current) => ({ ...current, visual_style: event.target.value as RenderOptions["visual_style"] }))}
                className="mt-1 w-full border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 outline-none focus:border-cyan-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              >
                <option value="blur">Blur background</option>
                <option value="crop">Center crop</option>
                <option value="zoom">Dynamic zoom</option>
                <option value="split">Split screen</option>
                <option value="clean">Clean frame</option>
              </select>
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            {(mode === "file" || youtubeProcessingMode === "manual") && (
              <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={burnCaptions}
                  disabled={uploading}
                  onChange={(event) => setBurnCaptions(event.target.checked)}
                  className="h-4 w-4 accent-violet-600"
                />
                Caption otomatis dari transkrip (bisa diedit per klip)
              </label>
            )}
            <p className="ml-auto border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300">
              Akselerasi otomatis — perangkat aktif tampil di status sistem.
            </p>
          </div>
        </section>

        {mode === "file" ? (
          <div
            onDragEnter={() => setDragActive(true)}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            className={`flex min-h-52 flex-col items-center justify-center rounded-2xl border border-dashed p-5 text-center transition ${
              dragActive
                ? "border-cyan-500 bg-cyan-50 dark:border-cyan-300 dark:bg-cyan-300/10"
                : "border-slate-300 bg-slate-50/70 hover:border-violet-300 hover:bg-violet-50/30 dark:border-slate-800 dark:bg-slate-950/40 dark:hover:border-violet-300/50"
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
              className="inline-flex items-center gap-2 rounded-lg bg-brand-strong px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand disabled:cursor-not-allowed disabled:opacity-60"
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
            <div
              role="status"
              className={`flex items-start justify-between gap-3 border px-3 py-2.5 text-xs ${
                youtubePreflight?.can_start
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-100"
                  : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100"
              }`}
            >
              <div className="flex min-w-0 items-start gap-2">
                {checkingYoutubePreflight ? <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
                <div>
                  <p className="font-semibold">
                    {checkingYoutubePreflight
                      ? "Memeriksa sesi YouTube"
                      : youtubePreflight?.can_start
                        ? "YouTube siap diproses"
                        : "YouTube belum siap"}
                  </p>
                  <p className="mt-0.5 leading-5">
                    {youtubePreflight?.message || youtubePreflightError || "Pemeriksaan lokal dijalankan sebelum job dibuat."}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => void refreshYoutubePreflight()}
                disabled={uploading || checkingYoutubePreflight}
                className="inline-flex shrink-0 items-center gap-1 border border-current/30 px-2 py-1 font-medium transition hover:bg-white/40 disabled:cursor-not-allowed disabled:opacity-60 dark:hover:bg-slate-950/20"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${checkingYoutubePreflight ? "animate-spin" : ""}`} aria-hidden="true" />
                Periksa ulang
              </button>
            </div>
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
            <p className="flex items-start gap-2 border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-100">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              ClipGen mengunduh dan memproses video penuh. Parameter timestamp YouTube seperti <code>?t=2601</code> tidak membatasi bagian video yang diproses.
            </p>

            {youtubeProcessingMode === "manual" && (
              <div className="grid gap-2 sm:grid-cols-1">
                <ToggleTile
                  icon={<Tags className="h-4 w-4" />}
                  label="Generate metadata"
                  active={manualYoutubeOptions.generate_metadata}
                  onClick={() => toggleManualOption("generate_metadata")}
                  disabled={uploading}
                />
              </div>
            )}

            <button
              onClick={handleYoutubeSubmit}
              disabled={uploading || checkingYoutubePreflight || !youtubeUrl.trim() || youtubePreflight?.can_start === false}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand-strong px-4 py-3 text-sm font-semibold text-white transition hover:bg-brand disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <SlidersHorizontal className="h-4 w-4" />}
              {uploading ? "Membuat job" : checkingYoutubePreflight ? "Memeriksa sesi" : "Proses"}
            </button>
          </div>
        )}

        {error && <p className="cg-alert">{error}</p>}
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
        active ? "rounded-lg bg-brand-strong text-white" : "rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
      }`}
      title={label}
    >
      {icon}
      {label}
    </button>
  );
}

function CampaignOption({
  active,
  disabled,
  title,
  description,
  onClick,
}: {
  active: boolean;
  disabled: boolean;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`group rounded-xl border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${
        active
          ? "border-violet-400 bg-violet-50 ring-1 ring-violet-300 dark:border-violet-300/70 dark:bg-violet-400/10 dark:ring-violet-300/30"
          : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white dark:border-slate-800 dark:bg-slate-900/50 dark:hover:border-slate-700 dark:hover:bg-slate-900"
      }`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className={`text-sm font-semibold ${active ? "text-violet-900 dark:text-violet-100" : "text-slate-900 dark:text-slate-100"}`}>{title}</span>
        {active ? <Check className="h-4 w-4 text-violet-600 dark:text-violet-300" /> : <ArrowUpRight className="h-4 w-4 text-slate-400 opacity-0 transition group-hover:opacity-100" />}
      </span>
      <span className="mt-1 block text-xs leading-5 text-slate-500 dark:text-slate-400">{description}</span>
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
          ? "bg-brand-strong text-white"
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
