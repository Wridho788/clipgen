import { expect, Page, Route, test } from "@playwright/test";

const now = "2026-08-08T10:00:00.000Z";

test.describe("ClipGen browser QA", () => {
  test("shows the server media timeout instead of a disconnected upload", async ({ page }) => {
    await mockApi(page, {});
    const detail = "File sudah diterima, tetapi pemeriksaan video/audio melewati batas waktu 60 detik. Job belum dibuat.";
    await page.route("**/api/videos/upload", (route) => route.fulfill({
      status: 504,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ detail }),
    }));
    await page.goto("/");
    await page.locator('input[type="file"]').setInputFiles({
      name: "video.mp4", mimeType: "video/mp4", buffer: Buffer.from("test upload"),
    });
    await expect(page.getByText(detail, { exact: true })).toBeVisible();
    await expect(page.getByText("Koneksi upload terputus.", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Pilih video" })).toBeEnabled();
  });

  test("explains an upload network failure without assuming the cause", async ({ page }) => {
    await mockApi(page, {});
    await page.route("**/api/videos/upload", (route) => route.abort("failed"));
    await page.goto("/");
    await page.locator('input[type="file"]').setInputFiles({
      name: "video.mp4", mimeType: "video/mp4", buffer: Buffer.from("test upload"),
    });
    await expect(page.getByText("Browser tidak dapat menerima respons upload dari server.", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pilih video" })).toBeEnabled();
  });

  test("queues a YouTube automatic job with lightweight defaults", async ({ page }) => {
    let receivedYoutubePost = "";
    const apiEvents: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/")) {
        apiEvents.push(`request ${request.method()} ${request.url()}`);
      }
    });
    page.on("requestfailed", (request) => {
      if (request.url().includes("/api/")) {
        apiEvents.push(`failed ${request.method()} ${request.url()} ${request.failure()?.errorText || ""}`);
      }
    });
    await mockApi(page, {
      jobs: [
        jobFixture({ id: "done-job-00000000", status: "done", progress: 100 }),
        jobFixture({ id: "failed-job-000000", status: "failed", progress: 0, error_message: "Interrupted" }),
      ],
      jobById: {
        "yt-job-1": jobFixture({
          id: "yt-job-1",
          source_type: "youtube_url",
          source_name: "https://youtube.com/watch?v=test",
          status: "downloading",
          progress: 5,
          stage_estimates: {
            downloading: 45,
            extracting: 10,
            transcribing: 60,
            cutting: 20,
            generating_metadata: 10,
          },
          current_stage_eta_seconds: 35,
          overall_eta_seconds: 120,
        }),
      },
      onYoutubePost: (postData) => {
        receivedYoutubePost = postData;
        return {
          job_id: "yt-job-1",
          status: "pending",
          estimated_processing_seconds: 120,
          stage_estimates: { downloading: 45, extracting: 10, transcribing: 60, cutting: 20, generating_metadata: 10 },
        };
      },
    });

    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Proyek", exact: true })).toBeVisible();
    await expect(page.getByText("v1.0.0")).toBeVisible();
    await expect(page.getByText("Worker")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pilih video" })).toBeVisible();
    await expect(page.getByText("done-job")).toBeVisible();

    await page.getByRole("button", { name: "YouTube" }).click();
    await page.getByRole("button", { name: "English" }).click();
    await expect(page.getByRole("button", { name: "Otomatis" })).toBeVisible();
    await page.getByPlaceholder("https://youtube.com/watch?v=...").fill("https://youtube.com/watch?v=test");
    await page.getByRole("button", { name: "Proses" }).click();

    await expect
      .poll(() => receivedYoutubePost || apiEvents.join("\n"), {
        message: `YouTube request was not completed. API events:\n${apiEvents.join("\n")}`,
      })
      .toContain("processing_mode");
    await expect(page).toHaveURL(/\/jobs\/yt-job-1$/, { timeout: 20_000 });
    await expect(page.getByText("Mengunduh YouTube").first()).toBeVisible();
    expect(receivedYoutubePost).toContain("en");
    expect(receivedYoutubePost).toContain("automatic");
    expect(receivedYoutubePost).toContain("generate_metadata");
    expect(receivedYoutubePost).toContain("true");
    expect(receivedYoutubePost).not.toContain("generate_highlights");
    expect(receivedYoutubePost).not.toContain("generate_subtitles");
    await expect(page.getByText("Analisis intro video")).toHaveCount(0);
  });

  test("queues a YouTube manual job with selected processing options", async ({ page }) => {
    let receivedYoutubePost = "";
    await mockApi(page, {
      onYoutubePost: (postData) => {
        receivedYoutubePost = postData;
        return {
          job_id: "yt-manual-1",
          status: "pending",
          estimated_processing_seconds: 160,
          stage_estimates: {
            downloading: 45,
            extracting: 5,
            transcribing: 30,
            cutting: 20,
            cropping: 20,
            generating_metadata: 10,
          },
        };
      },
    });

    await page.goto("/");
    await page.getByRole("button", { name: "YouTube" }).click();
    await page.getByRole("button", { name: "Manual" }).click();
    await page.getByLabel("Style visual").selectOption("crop");
    await page.getByPlaceholder("https://youtube.com/watch?v=...").fill("https://youtu.be/manual");
    await page.getByRole("button", { name: "Proses" }).click();

    await expect.poll(() => receivedYoutubePost).toContain("manual");
    expect(receivedYoutubePost).toContain("visual_style");
    expect(receivedYoutubePost).toContain("crop");
    expect(receivedYoutubePost).toContain("generate_metadata");
    expect(receivedYoutubePost).not.toContain("generate_highlights");
    expect(receivedYoutubePost).not.toContain("generate_subtitles");
    await expect(page).toHaveURL(/\/jobs\/yt-manual-1$/, { timeout: 20_000 });
  });

  test("does not create a YouTube job while the local access gate is blocked", async ({ page }) => {
    let youtubePosts = 0;
    await mockApi(page, {
      youtubePreflight: {
        can_start: false,
        status: "cookies_missing",
        message: "Sesi YouTube belum siap. Simpan cookies Netscape yang fresh.",
        retry_after_seconds: 0,
        cookies_ready: false,
      },
      onYoutubePost: () => {
        youtubePosts += 1;
        return {};
      },
    });

    await page.goto("/");
    await page.getByRole("button", { name: "YouTube" }).click();
    await expect(page.getByRole("status")).toContainText("YouTube belum siap");
    await expect(page.getByRole("status")).toContainText("cookies Netscape");
    await page.getByPlaceholder("https://youtube.com/watch?v=...").fill("https://youtu.be/blocked");
    await expect(page.getByRole("button", { name: "Proses" })).toBeDisabled();
    expect(youtubePosts).toBe(0);
  });

  test("requires an explicit confirmation before resetting the workspace", async ({ page }) => {
    let resetCalls = 0;
    await mockApi(page, {
      onStorageClear: () => {
        resetCalls += 1;
        return {
          mode: "permanent",
          files_handled: 4,
          bytes_moved: 0,
          bytes_reclaimed: 1024,
          jobs_deleted: 2,
          clips_deleted: 3,
          recycle_path: null,
        };
      },
    });

    await page.goto("/");
    await page.getByRole("button", { name: "Reset workspace" }).click();
    await expect(page.getByRole("dialog", { name: "Reset workspace" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Hapus semua data & job" })).toBeDisabled();
    await page.getByLabel(/Ketik HAPUS SEMUA/i).fill("HAPUS SEMUA");
    await page.getByRole("button", { name: "Hapus semua data & job" }).click();

    await expect.poll(() => resetCalls).toBe(1);
    await expect(page.getByRole("status")).toContainText("2 job, 3 klip");
  });

  test("shows upload job results without highlight or subtitle stages and edits clip metadata", async ({ page }) => {
    let clipTitle = "Moment Test";
    await mockApi(page, {
      jobById: {
        "done-job-1": jobFixture({
          id: "done-job-1",
          source_type: "upload",
          source_name: "sample-landscape.mp4",
          status: "done",
          progress: 100,
          stage_metrics: {
            extracting: 3,
            transcribing: 14,
            cutting: 5,
            generating_metadata: 6,
          },
          stage_estimates: {
            extracting: 4,
            transcribing: 20,
            cutting: 8,
            generating_metadata: 10,
          },
        }),
      },
      clipsByJob: {
        "done-job-1": () => [
          clipFixture({
            id: "clip-1",
            job_id: "done-job-1",
            title: clipTitle,
            caption: "Caption awal",
            hashtags: JSON.stringify(["clipgen", "qa"]),
          }),
          clipFixture({ id: "clip-2", job_id: "done-job-1", title: "Moment Kedua" }),
        ],
      },
      onClipPatch: async (route) => {
        const body = JSON.parse(route.request().postData() || "{}");
        clipTitle = body.title || clipTitle;
        await json(route, clipFixture({ id: "clip-1", job_id: "done-job-1", title: clipTitle }));
      },
    });

    await page.goto("/jobs/done-job-1");

    await expect(page.getByText("Selesai").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Klip" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pilih Moment Test" })).toBeVisible();
    await page.getByRole("button", { name: "Pilih Moment Kedua" }).click();
    await expect(page.getByText("Editor klip")).toBeVisible();
    await page.getByRole("button", { name: "Pilih Moment Test" }).click();
    await expect(page.getByText("Crop vertical")).toHaveCount(0);
    await expect(page.getByText("Subtitle")).toHaveCount(0);

    await page.getByRole("button", { name: "Edit" }).click();
    await page.getByPlaceholder("Judul").fill("Moment QA Final");
    await page.getByPlaceholder("Caption").fill("Caption update");
    await page.getByPlaceholder("hashtag1 hashtag2").fill("qa sprint3");
    await page.getByRole("button", { name: "Simpan" }).click();

    await expect(page.getByRole("button", { name: "Pilih Moment QA Final" })).toBeVisible();
    await page.getByRole("button", { name: "Klip relevan" }).click();
    await expect(page.getByRole("button", { name: "Klip relevan" })).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Trim" }).click();
    await page.getByRole("button", { name: "Render trim" }).click();
  });
});

type MockApiOptions = {
  jobs?: unknown[];
  jobById?: Record<string, unknown>;
  clipsByJob?: Record<string, unknown[] | (() => unknown[])>;
  onYoutubePost?: (postData: string) => unknown;
  youtubePreflight?: unknown;
  onClipPatch?: (route: Route) => Promise<void>;
  onStorageClear?: () => unknown;
};

async function mockApi(page: Page, options: MockApiOptions) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const path = url.pathname;

    if (method === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: corsHeaders("application/json"),
        body: "",
      });
      return;
    }

    if (method === "GET" && path === "/api/jobs") {
      await json(route, options.jobs || []);
      return;
    }

    if (method === "GET" && path === "/api/auth/config") {
      await json(route, { enabled: false, registration_enabled: false });
      return;
    }

    if (method === "GET" && path === "/api/system/metrics") {
      await json(route, systemMetricsFixture());
      return;
    }

    if (method === "GET" && path === "/api/system/release") {
      await json(route, releaseInfoFixture());
      return;
    }

    if (method === "GET" && path === "/api/videos/youtube/preflight") {
      await json(route, options.youtubePreflight || {
        can_start: true,
        status: "ready",
        message: "Sesi YouTube lokal siap.",
        retry_after_seconds: 0,
        cookies_ready: true,
      });
      return;
    }

    if (method === "POST" && path === "/api/system/storage/clear") {
      await json(route, options.onStorageClear?.() || {
        mode: "permanent",
        files_handled: 0,
        bytes_moved: 0,
        bytes_reclaimed: 0,
        jobs_deleted: 0,
        clips_deleted: 0,
        recycle_path: null,
      });
      return;
    }

    const jobMatch = path.match(/^\/api\/jobs\/([^/]+)$/);
    if (method === "GET" && jobMatch) {
      await json(route, options.jobById?.[jobMatch[1]] || jobFixture({ id: jobMatch[1] }));
      return;
    }

    if (method === "POST" && path === "/api/videos/youtube") {
      const postData = request.postData() || "";
      await json(route, options.onYoutubePost?.(postData) || {
        job_id: "yt-job-1",
        status: "pending",
        estimated_processing_seconds: 0,
        stage_estimates: {},
      });
      return;
    }

    const clipsByJobMatch = path.match(/^\/api\/clips\/job\/([^/]+)$/);
    if (method === "GET" && clipsByJobMatch) {
      const value = options.clipsByJob?.[clipsByJobMatch[1]] || [];
      await json(route, typeof value === "function" ? value() : value);
      return;
    }

    if (method === "PATCH" && path === "/api/clips/clip-1" && options.onClipPatch) {
      await options.onClipPatch(route);
      return;
    }

    if (method === "GET" && path === "/api/clips/clip-1/feedback") {
      await json(route, { rating: null, reason: null, positive_count: 0, negative_count: 0 });
      return;
    }

    if (method === "PUT" && path === "/api/clips/clip-1/feedback") {
      await json(route, { rating: 1, reason: null, positive_count: 1, negative_count: 0 });
      return;
    }

    if (method === "POST" && path === "/api/clips/clip-1/trim") {
      await json(route, clipFixture({ id: "clip-1", job_id: "done-job-1", status: "processing" }));
      return;
    }

    if (method === "GET" && /^\/api\/clips\/[^/]+\/preview$/.test(path)) {
      await route.fulfill({
        status: 200,
        headers: corsHeaders("video/mp4"),
        body: "",
      });
      return;
    }

    await route.fulfill({
      status: 404,
      headers: corsHeaders("application/json"),
      body: JSON.stringify({ detail: `No mock for ${method} ${path}` }),
    });
  });
}

async function json(route: Route, body: unknown) {
  await route.fulfill({
    status: 200,
    headers: corsHeaders("application/json"),
    body: JSON.stringify(body),
  });
}

function corsHeaders(contentType: string) {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers": "*",
    "access-control-allow-private-network": "true",
    "content-type": contentType,
  };
}

function jobFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    source_type: "upload",
    source_name: "sample.mp4",
    source_duration_seconds: 120,
    source_size_bytes: 1024,
    processing_options: JSON.stringify({
      min_clip_seconds: 15,
      max_clip_seconds: 60,
      clip_count: 5,
      metadata_language: "id",
      processing_mode: "manual",
      crop_vertical: false,
      generate_metadata: true,
      output_preset: "original",
      visual_style: "clean",
      render_acceleration: "auto",
    }),
    parent_job_id: null,
    retry_count: 0,
    status: "pending",
    progress: 0,
    error_message: null,
    warning_message: null,
    stage_metrics_json: null,
    stage_estimates_json: null,
    automatic_summary_json: null,
    stage_metrics: {},
    stage_estimates: {
      extracting: 4,
      transcribing: 20,
      cutting: 8,
      generating_metadata: 10,
    },
    automatic_summary: {},
    estimated_total_seconds: 47,
    current_stage_eta_seconds: 4,
    overall_eta_seconds: 47,
    estimated_completion_at: now,
    processing_started_at: now,
    completed_at: null,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

function clipFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: "clip-1",
    job_id: "job-1",
    start_time: 5,
    end_time: 25,
    file_path: "/app/storage/clips/clip-1.mp4",
    title: "Moment Test",
    caption: "Caption test",
    hashtags: JSON.stringify(["clipgen"]),
    status: "ready",
    created_at: now,
    ...overrides,
  };
}

function systemMetricsFixture() {
  return {
    queue: {
      queue_size: 0,
      worker_running: true,
      worker_started_at: now,
      current_job_id: null,
      current_job_started_at: null,
      processed_jobs: 3,
      failed_jobs: 0,
    },
    jobs: { done: 1, failed: 1 },
    clips: { ready: 2 },
    storage_bytes: {
      uploads: 1024 * 1024,
      clips: 512 * 1024,
      temp: 128 * 1024,
    },
    storage_policy: {
      temp_cleanup_enabled: true,
      temp_file_retention_hours: 24,
      upload_retention_days: 0,
      clip_retention_days: 0,
      permanent_asset_cleanup_enabled: false,
    },
    feedback: { positive: 0, negative: 0 },
  };
}

function releaseInfoFixture() {
  return {
    name: "ClipGen",
    version: "1.0.0",
    release_channel: "local-mvp",
    environment: "single-user-local",
    auth: { enabled: false, token_ttl_hours: 168 },
    limits: {
      max_upload_size_mb: 2048,
      youtube_download_timeout_seconds: 900,
      temp_file_retention_hours: 24,
    },
    defaults: {
      metadata_language: "id",
      whisper_model_size: "tiny",
      whisper_device: "cpu",
    },
    features: {
      local_upload: true,
      youtube_url: true,
      vertical_crop: true,
      youtube_manual_options: true,
      youtube_automatic_multi_clip: true,
      metadata_language_selector: true,
      playwright_e2e: true,
      clip_quality_feedback: true,
      local_multi_user: false,
    },
    known_risks: ["YouTube extraction can change."],
  };
}
