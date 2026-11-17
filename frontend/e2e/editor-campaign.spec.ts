import fs from "node:fs";
import path from "node:path";
import { expect, Page, Route, test } from "@playwright/test";

// The editor's Campaign tab: the rules a clip must satisfy, the backend's
// compliance findings, and a live duration check while trimming.
const FIXTURE = path.resolve(__dirname, "../../backend/tests/fixtures/media/speech_landscape.mp4");
const now = "2026-10-13T10:00:00.000Z";

const BRIEF = {
  id: "camp-1", name: "Promo Ramadan", description: "", platforms: ["tiktok"],
  min_clip_seconds: 15, max_clip_seconds: 30, hook_required: true, hook_max_seconds: 3,
  preferred_hook_types: [], required_visuals: ["Produk terlihat jelas"], required_phrases: ["Rumah di Luar Nalar"],
  prohibited_terms: ["diet"], hashtags: ["Promo", "Ramadan"], mentions: ["@akunresmi"],
  cta: "Klik link di bio", title_style: "curiosity_truthful", source_only: true, organic_only: false,
  avoid_misleading_edits: true, positive_brand_tone: false, allow_voiceover: false, retention_lock: false,
};

const COMPLIANCE = {
  status: "review_required",
  score: 40,
  checks: [
    { key: "duration", label: "Durasi klip", status: "pass", detail: "26.4 detik sesuai brief." },
    { key: "prohibited_terms", label: "Kata/tema terlarang", status: "pass", detail: "Tidak ada kata terlarang." },
    { key: "required_phrases", label: "Narasi wajib", status: "blocked", detail: "Frasa wajib belum ditemukan: Rumah di Luar Nalar" },
    { key: "hashtags", label: "Hashtag kampanye", status: "review_required", detail: "Tambahkan: #Ramadan" },
    { key: "visuals", label: "Kehadiran produk/visual wajib", status: "review_required", detail: "Konfirmasi manual: Produk terlihat jelas" },
  ],
};

function edit(trimStart = 7_050, trimEnd = 33_500) {
  return {
    schema_version: 1, trim_start_ms: trimStart, trim_end_ms: trimEnd, output_preset: "tiktok", visual_style: "crop",
    framing: { focus_x: 0.5, focus_y: 0.5 },
    captions: { enabled: true, style: { font_size: 64, text_color: "#FFFFFF", background: "outline", background_color: "#000000", position_y: 0.78, max_chars_per_line: 28, bold: true }, cues: [] },
    audio: { enabled: true, normalize: false }, watermark_enabled: false,
  };
}

function clipBody(withCampaign: boolean) {
  return {
    id: "clip-ed", job_id: "job-ed", start_time: 7.05, end_time: 33.5, suggested_start_time: 7.05, suggested_end_time: 33.5,
    file_path: "/app/storage/clips/clip-ed_r1.mp4", title: "Klip uji", caption: "Caption", hashtags: JSON.stringify(["Promo"]),
    status: "ready", review_status: "suggested", review_reason: null, position: 1,
    candidate: { algorithm_version: "transcript-boundary-v1", rank: 1, total: 1, score_meaning: "Peringkat relatif di dalam job ini.", signals: {}, explanation: ["Dibuka dengan pertanyaan."] },
    edit: edit(), edit_revision: 1, rendered_revision: 1, render_stale: false,
    render_error_code: null, render_error_message: null, render_report: null, exported_at: null,
    created_at: now, updated_at: now,
    distribution: withCampaign ? { campaign: { id: BRIEF.id, name: BRIEF.name, cta: BRIEF.cta, mentions: BRIEF.mentions, organic_only: false, retention_lock: false }, compliance: COMPLIANCE } : {},
  };
}

function job(withCampaign: boolean) {
  return {
    id: "job-ed", source_type: "upload", source_name: "speech_landscape.mp4", source_duration_seconds: 103.87,
    source_size_bytes: 2_354_975,
    processing_options: JSON.stringify({ output_preset: "tiktok", visual_style: "crop", ...(withCampaign ? { campaign_brief: BRIEF } : {}) }),
    parent_job_id: null, retry_count: 0, queue_position: null, status: "done", progress: 100, error_message: null,
    error_code: null, warning_message: null, stage_metrics_json: null, stage_estimates_json: null, automatic_summary_json: null,
    stage_metrics: {}, stage_estimates: {}, automatic_summary: {}, estimated_total_seconds: 0, current_stage_eta_seconds: 0,
    current_stage_elapsed_seconds: 0, overall_eta_seconds: 0,
    runtime: { label: "CPU", transcription_device: "cpu", render_device: "cpu", gpu_compatible: false },
    estimated_completion_at: null, processing_started_at: now, heartbeat_at: now, completed_at: now, created_at: now, updated_at: now,
  };
}

const VIDEO = fs.readFileSync(FIXTURE);

async function serveVideo(route: Route) {
  const range = route.request().headers()["range"];
  if (!range) {
    await route.fulfill({ status: 200, headers: { ...cors("video/mp4"), "accept-ranges": "bytes", "content-length": String(VIDEO.length) }, body: VIDEO });
    return;
  }
  const [startRaw, endRaw] = range.replace("bytes=", "").split("-");
  const start = Number(startRaw);
  const end = endRaw ? Number(endRaw) : VIDEO.length - 1;
  await route.fulfill({
    status: 206,
    headers: { ...cors("video/mp4"), "accept-ranges": "bytes", "content-range": `bytes ${start}-${end}/${VIDEO.length}`, "content-length": String(end - start + 1) },
    body: VIDEO.subarray(start, end + 1),
  });
}

function cors(contentType: string) {
  return { "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS", "access-control-allow-headers": "*", "content-type": contentType };
}

async function mockApi(page: Page, withCampaign: boolean) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const p = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors("application/json"), body: "" });
    if (/^\/api\/clips\/[^/]+\/preview$/.test(p)) return serveVideo(route);
    if (p === "/api/videos/job-ed/source") return serveVideo(route);
    const map: Record<string, unknown> = {
      "/api/auth/config": { enabled: false, registration_enabled: false },
      "/api/jobs/job-ed": job(withCampaign),
      "/api/clips/job/job-ed": [clipBody(withCampaign)],
      "/api/clips/clip-ed": clipBody(withCampaign),
      "/api/clips/clip-ed/feedback": { rating: null, reason: null, positive_count: 0, negative_count: 0 },
    };
    const body = map[p];
    await route.fulfill({ status: body ? 200 : 404, headers: cors("application/json"), body: JSON.stringify(body ?? { detail: `No mock for ${p}` }) });
  });
}

test.describe("Editor campaign panel", () => {
  test("lists the active rules and separates compliance findings by status", async ({ page }) => {
    await mockApi(page, true);
    await page.goto("/jobs/job-ed");
    await expect(page.getByText("Editor klip")).toBeVisible({ timeout: 60_000 });

    await page.getByRole("tab", { name: "Campaign" }).click();
    const panel = page.getByRole("tabpanel");

    await expect(panel.getByText("Promo Ramadan")).toBeVisible();
    // Scoped to the rules list: the live duration line quotes the same range.
    await expect(panel.locator("dd").filter({ hasText: "15–30 detik" })).toBeVisible();
    await expect(panel.locator("dd").filter({ hasText: "Rumah di Luar Nalar" })).toBeVisible();

    // Findings keep compliance separate from editorial quality and never show a percentage.
    await expect(panel.getByText("Frasa wajib belum ditemukan: Rumah di Luar Nalar")).toBeVisible();
    await expect(panel.getByText("Tambahkan: #Ramadan")).toBeVisible();
    await expect(panel.getByRole("heading", { name: /Gagal/ })).toBeVisible();
    await expect(panel.getByRole("heading", { name: /Perlu review/ })).toBeVisible();
    await expect(panel.getByRole("heading", { name: /Lolos/ })).toBeVisible();
    await expect(panel.getByText(/\d+%/)).toHaveCount(0);
    await expect(panel.getByText(/tidak menjamin|bukan jaminan/i)).toBeVisible();
    // Duration is stated once, by the live line, so a stale saved value cannot
    // contradict it on screen.
    await expect(panel.getByText("26.4 detik sesuai brief.")).toHaveCount(0);
    await expect(panel.getByTestId("campaign-live-duration")).toHaveCount(1);
  });

  test("the duration check follows the trim before the edit is saved", async ({ page }) => {
    await mockApi(page, true);
    await page.goto("/jobs/job-ed");
    await expect(page.getByText("Editor klip")).toBeVisible({ timeout: 60_000 });

    await page.getByRole("tab", { name: "Campaign" }).click();
    await expect(page.getByTestId("campaign-live-duration")).toContainText("26,5 detik");
    await expect(page.getByTestId("campaign-live-duration")).toContainText("sesuai");

    // Trim to 5 s, which is below the campaign's 15 s minimum.
    await page.getByRole("tab", { name: "Trim" }).click();
    await page.getByLabel("Akhir (m:ss.d)").fill("0:12.0");
    await page.getByLabel("Akhir (m:ss.d)").blur();
    await page.getByRole("tab", { name: "Campaign" }).click();
    await expect(page.getByTestId("campaign-live-duration")).toContainText("di luar");
    await expect(page.getByTestId("campaign-live-duration")).toContainText("15–30 detik");
  });

  test("without a campaign the tab is not offered", async ({ page }) => {
    await mockApi(page, false);
    await page.goto("/jobs/job-ed");
    await expect(page.getByText("Editor klip")).toBeVisible({ timeout: 60_000 });

    await expect(page.getByRole("tab", { name: "Campaign" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Trim" })).toBeVisible();
  });
});
