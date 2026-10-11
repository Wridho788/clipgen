import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";

// Full browser workflow against a running backend (real Whisper/FFmpeg).
// Opt-in because it takes minutes: E2E_REAL_BACKEND=1 npx playwright test e2e/real-backend.spec.ts
const FIXTURE = path.resolve(__dirname, "../../backend/tests/fixtures/media/speech_landscape.mp4");

test.describe("Real backend workflow", () => {
  test.skip(process.env.E2E_REAL_BACKEND !== "1", "set E2E_REAL_BACKEND=1 with the stack running");
  test.setTimeout(30 * 60_000);

  test("upload → candidates → edit captions and trim → render → reopen → download", async ({ page }, testInfo) => {
    await page.goto("/");
    // The fixture is English speech; Indonesian is the default audio language.
    await page.getByLabel("Bahasa audio").selectOption("en");
    await page.locator('input[type="file"]').setInputFiles(FIXTURE);
    await page.waitForURL(/\/jobs\/[^/]+$/, { timeout: 120_000 });
    const jobUrl = page.url();

    await expect(page.getByText("Editor klip")).toBeVisible({ timeout: 25 * 60_000 });
    await expect(page.getByTestId("candidate-rank")).toContainText("Peringkat #");
    await expect(page.getByText(/bukan prediksi views/)).toBeVisible();
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/);

    // Caption correction.
    await page.getByRole("tab", { name: "Caption" }).click();
    const firstCue = page.getByLabel("Teks caption 1", { exact: true });
    await expect(firstCue).not.toHaveValue("");
    await firstCue.fill("REAL E2E CAPTION");
    await firstCue.blur();
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/, { timeout: 15_000 });
    await page.getByRole("button", { name: "Putar caption 1", exact: true }).click();
    await expect(page.getByTestId("caption-overlay")).toHaveText("REAL E2E CAPTION", { timeout: 15_000 });

    // Trim the end by one second.
    await page.getByRole("tab", { name: "Trim" }).click();
    const before = await page.getByTestId("trim-duration").innerText();
    await page.getByRole("button", { name: "Akhir mundur 1 detik" }).click();
    await expect(page.getByTestId("trim-duration")).not.toHaveText(before);
    await expect(page.getByTestId("save-status")).toHaveText(/Tersimpan/, { timeout: 15_000 });
    await expect(page.getByTestId("render-state")).toContainText("belum mengikuti edit terbaru");

    // Render the saved revision and wait for validation.
    await page.getByRole("button", { name: "Render edit" }).click();
    await expect(page.getByTestId("render-state")).toContainText("File sesuai edit revisi", { timeout: 10 * 60_000 });
    await expect(page.getByTestId("validation-summary")).toContainText("Lolos validasi");
    await expect(page.getByTestId("validation-summary")).toContainText("1080×1920");

    // Reopen: edits persist.
    await page.goto(jobUrl);
    await expect(page.getByText("Editor klip")).toBeVisible({ timeout: 60_000 });
    await page.getByRole("tab", { name: "Caption" }).click();
    await expect(page.getByLabel("Teks caption 1", { exact: true })).toHaveValue("REAL E2E CAPTION");

    // Download and probe the exported MP4.
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download MP4" }).click();
    const download = await downloadPromise;
    const target = testInfo.outputPath("export.mp4");
    await download.saveAs(target);
    const probe = JSON.parse(
      execFileSync("ffprobe", ["-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", target]).toString(),
    );
    const video = probe.streams.find((stream: { codec_type: string }) => stream.codec_type === "video");
    expect([video.width, video.height]).toEqual([1080, 1920]);
    expect(probe.streams.some((stream: { codec_type: string }) => stream.codec_type === "audio")).toBe(true);
  });
});
