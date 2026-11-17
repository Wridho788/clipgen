import { expect, Page, Route, test } from "@playwright/test";

const now = "2026-10-12T10:00:00.000Z";

type Json = Record<string, unknown>;

const RULES = {
  id: "c1", name: "Promo Ramadan", description: "", platforms: ["tiktok"], min_clip_seconds: 30, max_clip_seconds: 60,
  hook_required: true, hook_max_seconds: 3, preferred_hook_types: [], required_visuals: [], required_phrases: [],
  prohibited_terms: [], hashtags: ["Promo"], mentions: [], cta: "Klik link di bio", title_style: "curiosity_truthful",
  source_only: true, organic_only: false, avoid_misleading_edits: true, positive_brand_tone: false,
  allow_voiceover: false, retention_lock: false,
};

function configuration(version: number, overrides: Json = {}) {
  return {
    campaign_id: "c1", version, raw_source_text: "Teks asli campaign", user_confirmed_at: now, created_at: now,
    config: {
      schema_version: 1, objective: "", brief: "", target_audience: "", platforms: ["tiktok"], rules: RULES,
      soft_preferences: [], reward_details: null, unresolved_items: [],
    },
    ...overrides,
  };
}

function campaignDetail(version = 1, overrides: Json = {}) {
  return {
    id: "c1", name: "Promo Ramadan", type: "custom", source: "manual_import", source_name: null, source_url: null,
    status: "active", latest_version: version, confirmed: true, created_at: now, updated_at: now,
    configuration: configuration(version), ...overrides,
  };
}

function field(status: string, value: unknown = null, evidence: string[] = [], note: string | null = null) {
  return { status, value, evidence, note };
}

const NOT_PROVIDED = field("not_provided");

function draft(fields: Record<string, unknown>, extra: Json = {}) {
  return {
    raw_source_text: "Campaign Promo Ramadan\nDurasi 30-60 detik", truncated: false,
    fields: {
      min_clip_seconds: NOT_PROVIDED, max_clip_seconds: NOT_PROVIDED, hashtags: NOT_PROVIDED, mentions: NOT_PROVIDED,
      platforms: NOT_PROVIDED, source_urls: NOT_PROVIDED, prohibited_terms: NOT_PROVIDED, cta: NOT_PROVIDED,
      dates: NOT_PROVIDED, ...fields,
    },
    unresolved_items: [], warnings: [], ...extra,
  };
}

async function respond(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
      "access-control-allow-headers": "*",
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

/** Routes only what these flows need; anything else is a 404 so a stray call fails loudly. */
async function mockApi(page: Page, handlers: Record<string, (route: Route) => Promise<void> | void>) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") return respond(route, {}, 204);
    if (path === "/api/auth/config") return respond(route, { enabled: false, registration_enabled: false });
    const handler = handlers[`${request.method()} ${path}`];
    if (handler) return handler(route);
    return respond(route, { detail: `No mock for ${request.method()} ${path}` }, 404);
  });
}

test.describe("Campaign import and management", () => {
  test("ambiguous findings block saving until reviewed, then the confirmed campaign is saved", async ({ page }) => {
    let saved: Json | null = null;
    await mockApi(page, {
      "POST /api/campaigns/analyze": (route) => respond(route, draft({
        min_clip_seconds: field("needs_review", null, ["30-60 detik", "15-90 detik"], "Pernyataan durasi bertentangan"),
        max_clip_seconds: field("needs_review", null, ["30-60 detik", "15-90 detik"], "Pernyataan durasi bertentangan"),
        hashtags: field("found", ["Promo"], ["#Promo"]),
      }, { unresolved_items: ["Durasi minimum bertentangan di teks (15 vs 30 detik); pilih satu nilai."] })),
      "POST /api/campaigns": (route) => {
        saved = route.request().postDataJSON();
        return respond(route, campaignDetail(1), 201);
      },
      "GET /api/campaigns/c1": (route) => respond(route, campaignDetail(1)),
      "GET /api/campaigns/c1/versions": (route) => respond(route, [configuration(1)]),
    });

    await page.goto("/campaigns/new");
    await expect(page.getByRole("button", { name: "Analisa Campaign" })).toBeDisabled();
    await page.getByLabel("Teks campaign").fill("Campaign Promo Ramadan\nDurasi 30-60 detik. Catatan: durasi 15-90 detik. #Promo");
    await page.getByRole("button", { name: "Analisa Campaign" }).click();

    await expect(page.getByRole("heading", { name: "2. Periksa dan koreksi" })).toBeVisible();
    await expect(page.getByText("Perlu review", { exact: true })).toBeVisible();
    await expect(page.getByText("Ditemukan", { exact: true })).toBeVisible();
    await expect(page.getByText("Durasi minimum bertentangan di teks")).toBeVisible();
    await expect(page.getByLabel("Nama campaign")).toHaveValue("Campaign Promo Ramadan");
    // The conflicting duration is not guessed: the form keeps the default and waits for the user.
    await expect(page.getByLabel("Durasi minimum (detik)")).toHaveValue("15");

    const save = page.getByRole("button", { name: "Konfirmasi & Simpan" });
    await expect(save).toBeDisabled();
    await expect(page.getByText("1 bagian masih perlu kamu periksa dan centang.")).toBeVisible();

    await page.getByLabel("Durasi minimum (detik)").fill("30");
    await page.getByLabel("Durasi maksimum (detik)").fill("60");
    await expect(save).toBeDisabled(); // editing alone is not an acknowledgement
    await page.getByLabel("Saya sudah memeriksa bagian “Durasi klip (detik)”").check();
    await expect(save).toBeEnabled();
    await save.click();

    // First visit to a dynamic route compiles it in `next dev`, which can take a while.
    await expect(page).toHaveURL(/\/campaigns\/c1$/, { timeout: 45_000 });
    expect(saved).toMatchObject({
      name: "Campaign Promo Ramadan", type: "custom", source: "manual_import", confirmed: true,
      raw_source_text: "Campaign Promo Ramadan\nDurasi 30-60 detik",
    });
    const config = (saved as unknown as { config: { rules: Json; unresolved_items: string[] } }).config;
    expect(config.rules).toMatchObject({ min_clip_seconds: 30, max_clip_seconds: 60, hashtags: ["Promo"] });
    expect(config.unresolved_items).toHaveLength(1);
  });

  test("a duration above ClipGen's 120 second limit cannot be saved until corrected", async ({ page }) => {
    await mockApi(page, {
      "POST /api/campaigns/analyze": (route) => respond(route, draft({
        min_clip_seconds: field("needs_review", 180, ["3-5 menit"], "Melebihi batas 120 detik yang didukung ClipGen"),
        max_clip_seconds: field("needs_review", 300, ["3-5 menit"], "Melebihi batas 120 detik yang didukung ClipGen"),
      })),
    });
    await page.goto("/campaigns/new");
    await page.getByLabel("Teks campaign").fill("Durasi 3-5 menit");
    await page.getByRole("button", { name: "Analisa Campaign" }).click();

    await page.getByLabel("Saya sudah memeriksa bagian “Durasi klip (detik)”").check();
    await expect(page.getByRole("alert").filter({ hasText: "antara 5 dan 120 detik" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Konfirmasi & Simpan" })).toBeDisabled();

    await page.getByLabel("Durasi minimum (detik)").fill("60");
    await page.getByLabel("Durasi maksimum (detik)").fill("120");
    await expect(page.getByRole("button", { name: "Konfirmasi & Simpan" })).toBeEnabled();
  });

  test("an analysis error is shown and nothing is saved", async ({ page }) => {
    let posts = 0;
    await mockApi(page, {
      "POST /api/campaigns/analyze": (route) => respond(route, { detail: "Teks campaign kosong" }, 422),
      "POST /api/campaigns": (route) => { posts += 1; return respond(route, campaignDetail(1), 201); },
    });
    await page.goto("/campaigns/new");
    await page.getByLabel("Teks campaign").fill("x");
    await page.getByRole("button", { name: "Analisa Campaign" }).click();

    await expect(page.getByRole("alert").filter({ hasText: "Teks campaign kosong" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2. Periksa dan koreksi" })).toHaveCount(0);
    expect(posts).toBe(0);
  });

  test("editing a saved campaign creates a new version and keeps the old one readable", async ({ page }) => {
    let version = 1;
    let update: Json | null = null;
    await mockApi(page, {
      "GET /api/campaigns/c1": (route) => respond(route, campaignDetail(version)),
      "GET /api/campaigns/c1/versions": (route) => respond(route, Array.from({ length: version }, (_, index) => configuration(index + 1))),
      "PUT /api/campaigns/c1": (route) => {
        update = route.request().postDataJSON();
        version = 2;
        return respond(route, campaignDetail(2));
      },
    });
    await page.goto("/campaigns/c1");
    await expect(page.getByRole("heading", { name: "Promo Ramadan" })).toBeVisible();
    await expect(page.getByText("30–60 detik")).toBeVisible();

    await page.getByRole("button", { name: "Edit aturan" }).click();
    await expect(page.getByText("Menyimpan akan membuat versi 2.")).toBeVisible();
    await page.getByLabel("Durasi maksimum (detik)").fill("45");
    await page.getByRole("button", { name: "Simpan sebagai versi baru" }).click();

    await expect(page.getByRole("button", { name: "Edit aturan" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Versi 1/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Versi 2/ })).toBeVisible();
    expect(update).toMatchObject({ confirmed: true, raw_source_text: "Teks asli campaign" });
    expect((update as unknown as { config: { rules: Json } }).config.rules).toMatchObject({ min_clip_seconds: 30, max_clip_seconds: 45, hashtags: ["Promo"], cta: "Klik link di bio" });
  });

  test("the upload form offers saved campaigns and sends the campaign id, not an inline brief", async ({ page }) => {
    let uploadBody = "";
    await mockApi(page, {
      "GET /api/jobs": (route) => respond(route, []),
      "GET /api/system/metrics": (route) => respond(route, {
        queue: { queue_size: 0, worker_running: true, worker_started_at: now, current_job_id: null, current_job_started_at: null, processed_jobs: 0, failed_jobs: 0 },
        jobs: {}, clips: {}, storage_bytes: { uploads: 0, clips: 0, temp: 0 },
        storage_policy: { temp_cleanup_enabled: true, temp_file_retention_hours: 24, upload_retention_days: 0, clip_retention_days: 0, permanent_asset_cleanup_enabled: false },
        feedback: { positive: 0, negative: 0 },
      }),
      "GET /api/system/release": (route) => respond(route, {
        name: "ClipGen", version: "1.0.0", release_channel: "local", environment: "local", auth: { enabled: false, token_ttl_hours: 1 },
        limits: { max_upload_size_mb: 2048, youtube_download_timeout_seconds: 900, temp_file_retention_hours: 24 },
        defaults: { metadata_language: "id", whisper_model_size: "small", whisper_device: "cpu" }, features: {}, known_risks: [],
      }),
      "GET /api/campaigns": (route) => respond(route, [{ ...campaignDetail(3), configuration: undefined }]),
      "GET /api/campaigns/c1": (route) => respond(route, campaignDetail(3)),
      "POST /api/videos/upload": (route) => {
        uploadBody = route.request().postData() || "";
        return respond(route, { job_id: "job-1", status: "pending", estimated_processing_seconds: 0, stage_estimates: {} });
      },
      "GET /api/jobs/job-1": (route) => respond(route, { detail: "stop here" }, 404),
    });
    await page.goto("/");
    await page.getByRole("button", { name: /Promo Ramadan/ }).click();
    await expect(page.getByText("Guideline aktif · versi 3")).toBeVisible();
    await page.locator('input[type="file"]').setInputFiles({ name: "video.mp4", mimeType: "video/mp4", buffer: Buffer.from("video") });

    await expect.poll(() => uploadBody).not.toBe("");
    expect(uploadBody).toContain('name="campaign_id"');
    expect(uploadBody).toContain("c1");
    expect(uploadBody).toContain('name="campaign_configuration_version"');
    expect(uploadBody).not.toContain("campaign_brief_json");
    expect(uploadBody).toMatch(/name="min_clip_seconds"\r\n\r\n30/);
    expect(uploadBody).toMatch(/name="max_clip_seconds"\r\n\r\n60/);
  });
});
