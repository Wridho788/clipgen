/**
 * Capture ClipGen screenshots for the Gemini integration write-up.
 *
 * Usage:
 *   node scripts/screenshot_gemini.mjs <jobId> <outDir>
 *
 * The backend must be running on :8000 and the frontend on :3000.
 *
 * Playwright is installed in frontend/node_modules, so it is imported through a
 * relative path; a bare "@playwright/test" specifier does not resolve from
 * this directory (the repo root has no node_modules of its own).
 */
import pw from "../frontend/node_modules/@playwright/test/index.js";
import { mkdir } from "node:fs/promises";

const { chromium } = pw;

const jobId = process.argv[2];
const outDir = process.argv[3] ?? "docs/screenshots/gemini";
const API = "http://localhost:8000";
const WEB = "http://localhost:3000";

if (!jobId) {
  console.error("usage: node scripts/screenshot_gemini.mjs <jobId> <outDir>");
  process.exit(2);
}

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
const page = await context.newPage();

async function shot(name) {
  const path = `${outDir}/${name}.png`;
  await page.screenshot({ path, fullPage: false });
  console.log(`saved ${path}`);
}

// 1. Dashboard
await page.goto(WEB, { waitUntil: "domcontentloaded" });
await page.locator('a[href^="/jobs/"]').first().waitFor({ timeout: 60000 });
await page.waitForTimeout(1500);
await shot("01-dashboard");

// 1b. The project list at the bottom of the dashboard
await page.getByText("Proyek terbaru").scrollIntoViewIfNeeded();
await page.waitForTimeout(800);
await shot("01b-dashboard-projects");

// 2. Job detail with the generated clips.
//    The job page polls the API, so "networkidle" never settles here.
await page.goto(`${WEB}/jobs/${jobId}`, { waitUntil: "domcontentloaded" });
await page.getByText("Pilih klip untuk diedit").waitFor({ timeout: 60000 });
await page.waitForTimeout(2000);
await shot("02-job-clips");

// 3. Metadata tab of the editor: the Gemini title, caption, and hashtags
const metadataTab = page.getByRole("tab", { name: /Metadata & distribusi/i }).first();
await metadataTab.click();
await page.waitForTimeout(1500);
await metadataTab.scrollIntoViewIfNeeded();
await page.waitForTimeout(600);
await shot("03-metadata-gemini");

// 4. Regenerate the metadata through the "Buat ulang dengan AI" button
const before = await fetch(`${API}/api/clips/job/${jobId}`).then((r) => r.json());
const regenerate = page.getByRole("button", { name: /Buat ulang dengan AI/i }).first();
await regenerate.scrollIntoViewIfNeeded();
await regenerate.click();
await page.waitForTimeout(1200);
await shot("04-regenerate-inflight");

await page.waitForFunction(
  () => !document.body.innerText.includes("Membuat..."),
  undefined,
  { timeout: 120000 }
);
await page.waitForTimeout(1500);
await shot("05-regenerate-done");

const after = await fetch(`${API}/api/clips/job/${jobId}`).then((r) => r.json());
const pick = (clips) =>
  clips.map((c) => ({ title: c.title, hashtags: c.hashtags }));
console.log("before:", JSON.stringify(pick(before), null, 2));
console.log("after :", JSON.stringify(pick(after), null, 2));

// 5. Health probe: shows the Gemini provider as configured
const health = await (await fetch(`${API}/health/ready`)).json();
console.log("health:", JSON.stringify(health, null, 2));

await browser.close();
