import fs from "node:fs";
import path from "node:path";
import { expect, Page, Route, test } from "@playwright/test";

// Fast, deterministic editor checks: the API is mocked, but the preview plays
// the real fixture video so caption overlay timing is exercised in a browser.
const FIXTURE = path.resolve(__dirname, "../../backend/tests/fixtures/media/speech_landscape.mp4");
const now = "2026-10-10T10:00:00.000Z";

type EditState = {
  revision: number;
  renderedRevision: number;
  status: "ready" | "processing";
  review: string;
  reviewReason: string | null;
  edit: Record<string, unknown>;
  saves: Array<{ base_revision: number; edit: Record<string, any> }>;
  renders: number;
  conflictNext: boolean;
};

function initialEdit() {
  return {
    schema_version: 1,
    trim_start_ms: 7_050,
    trim_end_ms: 33_500,
    output_preset: "tiktok",
    visual_style: "crop",
    framing: { focus_x: 0.5, focus_y: 0.5 },
    captions: {
      enabled: true,
      style: { font_size: 64, text_color: "#FFFFFF", background: "outline", background_color: "#000000", position_y: 0.78, max_chars_per_line: 28, bold: true },
      cues: [
        { id: "cue-1", start_ms: 7_200, end_ms: 9_800, text: "So here is the question", original_text: "So here is the question" },
        { id: "cue-2", start_ms: 9_800, end_ms: 12_700, text: "everyone asks me", original_text: "everyone asks me" },
        { id: "cue-3", start_ms: 40_000, end_ms: 41_000, text: "outside the trim", original_text: "outside the trim" },
      ],
    },
    audio: { enabled: true, normalize: false },
    watermark_enabled: false,
  };
}

function clipBody(state: EditState) {
  return {
    id: "clip-ed",
    job_id: "job-ed",
    start_time: (state.edit.trim_start_ms as number) / 1000,
    end_time: (state.edit.trim_end_ms as number) / 1000,
    suggested_start_time: 7.05,
    suggested_end_time: 33.5,
    file_path: "/app/storage/clips/clip-ed_r1.mp4",
    title: "Why side projects never launch",
    caption: "Caption",
    hashtags: JSON.stringify(["clipgen"]),
    status: state.status,
    review_status: state.review,
    review_reason: state.reviewReason,
    position: 1,
    candidate: {
      algorithm_version: "transcript-boundary-v1",
      rank: 1,
      total: 1,
      score_meaning: "Peringkat relatif di dalam job ini, bukan prediksi views atau viralitas.",
      signals: { complete_ending: 1, opening_hook: 1 },
      explanation: ["Dibuka dengan pertanyaan atau kalimat pemancing.", "Berakhir di akhir kalimat."],
    },
    edit: state.edit,
    edit_revision: state.revision,
    rendered_revision: state.renderedRevision,
    render_stale: state.renderedRevision < state.revision,
    render_error_code: null,
    render_error_message: null,
    render_report: {
      revision: state.renderedRevision,
      rendered_at: now,
      render_seconds: 4.2,
      encoder: "libx264",
      captions_rendered: 2,
      validation: {
        ok: true,
        checks: { exists: true, non_empty: true, probeable: true, dimensions: true, duration: true, audio: true, decodable: true },
        problems: [],
        width: 1080,
        height: 1920,
        duration_seconds: ((state.edit.trim_end_ms as number) - (state.edit.trim_start_ms as number)) / 1000,
        has_audio: true,
        size_bytes: 2_000_000,
      },
    },
    exported_at: null,
    created_at: now,
    updated_at: now,
  };
}

async function mockEditorApi(page: Page, state: EditState) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const pathname = url.pathname;
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: cors("application/json"), body: "" });
    if (pathname === "/api/auth/config") return json(route, { enabled: false, registration_enabled: false });
    if (pathname === "/api/system/metrics") return json(route, { queue: { queue_size: 0, worker_running: true }, jobs: {}, clips: {}, storage_bytes: {}, storage_policy: {}, feedback: {} });
    if (pathname === "/api/system/release") return json(route, { name: "ClipGen", version: "1.0.0", features: {}, known_risks: [], limits: {}, defaults: {}, auth: { enabled: false } });
    if (pathname === "/api/jobs/job-ed") return json(route, job());
    if (pathname === "/api/clips/job/job-ed") return json(route, [clipBody(state)]);
    if (pathname === "/api/clips/clip-ed" && method === "GET") return json(route, clipBody(state));
    if (pathname === "/api/clips/clip-ed/feedback") return json(route, { rating: null, reason: null, positive_count: 0, negative_count: 0 });
    if (pathname === "/api/clips/clip-ed/source" || pathname === "/api/clips/clip-ed/preview") {
      return serveVideo(route);
    }
    if (pathname === "/api/clips/clip-ed/edit" && method === "PUT") {
      const body = JSON.parse(request.postData() || "{}");
      state.saves.push(body);
      if (state.conflictNext) {
        state.conflictNext = false;
        return route.fulfill({ status: 409, headers: cors("application/json"), body: JSON.stringify({ detail: "Ada versi edit yang lebih baru.", code: "EDIT_CONFLICT" }) });
      }
      if (body.base_revision !== state.revision) {
        return route.fulfill({ status: 409, headers: cors("application/json"), body: JSON.stringify({ detail: "stale", code: "EDIT_CONFLICT" }) });
      }
      state.revision += 1;
      state.edit = body.edit;
      if (state.review === "suggested") state.review = "edited";
      return json(route, clipBody(state));
    }
    if (pathname === "/api/clips/clip-ed/render" && method === "POST") {
      state.renders += 1;
      state.status = "processing";
      const response = clipBody(state);
      // Finish the "render" shortly after so polling observes the transition.
      setTimeout(() => {
        state.status = "ready";
        state.renderedRevision = state.revision;
      }, 1200);
      return route.fulfill({ status: 202, headers: cors("application/json"), body: JSON.stringify(response) });
    }
    if (pathname === "/api/clips/clip-ed/review" && method === "POST") {
      const body = JSON.parse(request.postData() || "{}");
      state.review = body.status;
      state.reviewReason = body.reason || null;
      return json(route, clipBody(state));
    }
    return route.fulfill({ status: 404, headers: cors("application/json"), body: JSON.stringify({ detail: `No mock for ${method} ${pathname}` }) });
  });
}

test.describe("Clip editor", () => {
  let state: EditState;

  test.beforeEach(async ({ page }) => {
    state = { revision: 1, renderedRevision: 1, status: "ready", review: "suggested", reviewReason: null, edit: initialEdit(), saves: [], renders: 0, conflictNext: false };
    await mockEditorApi(page, state);
    await page.goto("/jobs/job-ed");
    await expect(page.getByText("Editor klip")).toBeVisible({ timeout: 30_000 });
  });

  test("shows candidate explanation without a percentage score", async ({ page }) => {
    await expect(page.getByTestId("candidate-rank")).toContainText("Peringkat #1 dari 1");
    await expect(page.getByText("Dibuka dengan pertanyaan atau kalimat pemancing.")).toBeVisible();
    await expect(page.getByText(/bukan prediksi views/)).toBeVisible();
    await expect(page.getByText(/\d+%\s*(viral|score)/i)).toHaveCount(0);
  });

  test("trims, edits captions, autosaves, previews the caption, and renders the saved revision", async ({ page }) => {
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/);

    // Trim: nudge start forward one second.
    await page.getByRole("button", { name: "Mulai maju 1 detik" }).click();
    await expect(page.getByTestId("trim-duration")).toContainText("25.4 detik");
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/, { timeout: 5000 });
    expect(state.saves.at(-1)?.edit.trim_start_ms).toBe(8_050);
    await expect(page.getByTestId("render-state")).toContainText("belum mengikuti edit terbaru");

    // Captions: correct the first cue and switch to a yellow box style.
    await page.getByRole("tab", { name: "Caption" }).click();
    await expect(page.getByText("di luar trim", { exact: true })).toBeVisible();
    const firstCue = page.getByLabel("Teks caption 1", { exact: true });
    await firstCue.fill("So here is THE question");
    await firstCue.blur();
    await page.getByLabel("Latar").selectOption("box");
    await page.getByRole("button", { name: "Warna teks #FFE14D" }).click();
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/, { timeout: 5000 });
    const savedCaptions = state.saves.at(-1)?.edit.captions;
    expect(savedCaptions.cues[0].text).toBe("So here is THE question");
    expect(savedCaptions.cues[0].original_text).toBe("So here is the question");
    expect(savedCaptions.style.background).toBe("box");
    expect(savedCaptions.style.text_color).toBe("#FFE14D");
    await expect(page.getByText("dikoreksi", { exact: true })).toBeVisible();

    // Preview overlay shows the corrected text at that cue's time.
    await page.getByRole("button", { name: "Putar caption 1", exact: true }).click();
    await expect(page.getByTestId("caption-overlay")).toHaveText("So here is THE question");
    await expect(page.getByTestId("caption-overlay")).toHaveCSS("color", "rgb(255, 225, 77)");

    // Undo restores the previous style, redo re-applies it.
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(page.getByTestId("caption-overlay")).toHaveCSS("color", "rgb(255, 255, 255)");
    await page.getByRole("button", { name: "Redo" }).click();
    await expect(page.getByTestId("caption-overlay")).toHaveCSS("color", "rgb(255, 225, 77)");
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/, { timeout: 5000 });

    // Render uses the saved revision and reports validation.
    await page.getByRole("button", { name: "Render edit" }).click();
    await expect(page.getByTestId("render-state")).toContainText(`File sesuai edit revisi ${state.revision}`, { timeout: 10000 });
    await expect(page.getByTestId("validation-summary")).toContainText("Lolos validasi");
    expect(state.renders).toBe(1);
  });

  test("framing and format changes are saved into the edit document", async ({ page }) => {
    await page.getByRole("tab", { name: "Format & framing" }).click();
    await page.getByRole("button", { name: "Zoom 1.12×" }).click();
    await page.getByLabel(/Posisi horizontal/).fill("30");
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/, { timeout: 5000 });
    const saved = state.saves.at(-1)?.edit;
    expect(saved.visual_style).toBe("zoom");
    expect(saved.framing.focus_x).toBeCloseTo(0.3);
    await expect(page.getByTestId("editor-canvas")).toHaveAttribute("style", /aspect-ratio: 1080 \/ 1920/);
  });

  test("rejecting requires a reason and is reflected in the gallery", async ({ page }) => {
    await page.getByRole("button", { name: "Tolak…" }).click();
    await page.getByLabel("Alasan").selectOption("bad_boundaries");
    await page.getByRole("button", { name: "Tolak kandidat" }).click();
    await expect(page.getByTestId("review-status")).toContainText("Ditolak · Batas awal/akhir buruk");
    await expect(page.getByRole("button", { name: /Pilih .*\(Ditolak\)/ })).toBeVisible();
    expect(state.reviewReason).toBe("bad_boundaries");
  });

  test("an edit conflict is surfaced instead of overwriting newer work", async ({ page }) => {
    state.conflictNext = true;
    await page.getByRole("button", { name: "Akhir mundur 1 detik" }).click();
    await expect(page.getByTestId("save-status")).toHaveText(/Konflik versi/, { timeout: 5000 });
    await expect(page.getByRole("button", { name: "Muat versi terbaru" })).toBeVisible();
    await page.getByRole("button", { name: "Muat versi terbaru" }).click();
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/);
    await expect(page.getByTestId("trim-duration")).toContainText("26.4 detik");
  });

  test("keyboard shortcuts set trim boundaries from the playhead", async ({ page }) => {
    await page.getByRole("tab", { name: "Trim" }).click();
    await page.locator("body").click({ position: { x: 5, y: 5 } });
    await page.evaluate(() => {
      const video = document.querySelector<HTMLVideoElement>("[data-testid=editor-canvas] video");
      if (video) video.currentTime = 10;
    });
    await page.keyboard.press("i");
    await expect(page.getByLabel("Mulai (m:ss.d)")).toHaveValue("0:10.0");
  });
});

function job() {
  return {
    id: "job-ed", source_type: "upload", source_name: "speech_landscape.mp4", source_duration_seconds: 103.87,
    source_size_bytes: 2_354_975, processing_options: JSON.stringify({ output_preset: "tiktok", visual_style: "crop" }),
    parent_job_id: null, retry_count: 0, queue_position: null, status: "done", progress: 100, error_message: null,
    error_code: null, warning_message: null, stage_metrics_json: null, stage_estimates_json: null, automatic_summary_json: null,
    stage_metrics: { transcribing: 60, cropping: 20 }, stage_estimates: { transcribing: 60, cropping: 20 }, automatic_summary: {},
    estimated_total_seconds: 80, current_stage_eta_seconds: 0, current_stage_elapsed_seconds: 0, overall_eta_seconds: 0,
    runtime: { label: "CPU", transcription_device: "cpu", render_device: "cpu", gpu_compatible: false },
    estimated_completion_at: null, processing_started_at: now, heartbeat_at: now, completed_at: now, created_at: now, updated_at: now,
  };
}

// Byte-range responses like the backend's media_file_response, so the browser can seek.
const VIDEO = fs.readFileSync(FIXTURE);
async function serveVideo(route: Route) {
  const range = route.request().headers()["range"];
  const match = range?.match(/bytes=(\d*)-(\d*)/);
  if (!match) {
    return route.fulfill({ status: 200, body: VIDEO, headers: { ...cors("video/mp4"), "accept-ranges": "bytes" } });
  }
  const start = match[1] ? Number(match[1]) : Math.max(0, VIDEO.length - Number(match[2]));
  const end = match[1] && match[2] ? Math.min(Number(match[2]), VIDEO.length - 1) : VIDEO.length - 1;
  return route.fulfill({
    status: 206,
    body: VIDEO.subarray(start, end + 1),
    headers: { ...cors("video/mp4"), "accept-ranges": "bytes", "content-range": `bytes ${start}-${end}/${VIDEO.length}` },
  });
}

async function json(route: Route, body: unknown) {
  await route.fulfill({ status: 200, headers: cors("application/json"), body: JSON.stringify(body) });
}

function cors(contentType: string) {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers": "*",
    "content-type": contentType,
  };
}
