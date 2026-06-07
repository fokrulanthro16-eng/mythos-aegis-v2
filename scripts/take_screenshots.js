// Playwright screenshot capture for Mythos Aegis admin console
// Run: node scripts/take_screenshots.js
// Requires: backend on :8000, admin UI on :3001, Playwright Chromium installed
//
// Outputs to: docs/screenshots/

const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = "http://localhost:3001";
const TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJ0ZW5hbnRfaWQiOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJpc3MiOiJteXRob3MtYWVnaXMiLCJhdWQiOiJteXRob3MtYWVnaXMtYXBpIiwiaWF0IjoxNzgwODU3OTU5LCJleHAiOjE3ODA5NDQzNTksInJvbGVzIjpbImFkbWluIl0sInBlcm1pc3Npb25zIjpbInJhZy51cGxvYWQiLCJyYWcuc2VhcmNoIiwicmFnLmFzayIsInZpc2lvbi5hbmFseXplIiwidmlzaW9uLmV4dHJhY3QiLCJhZ2VudC5ydW4iLCJhZ2VudC5zZXNzaW9ucy5yZWFkIiwiYWdlbnQuc2Vzc2lvbnMud3JpdGUiLCJiaWxsaW5nLnJlYWQiLCJiaWxsaW5nLm1hbmFnZSJdfQ.6-dLX_vGidvSkAPh932rx_YUa5Z9KbHyEYdXZbaoNtI";
const PROJECT_ID = "22222222-2222-2222-2222-222222222222";
const OUT_DIR = path.join(__dirname, "..", "docs", "screenshots");

fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(page, name, opts = {}) {
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: opts.fullPage ?? false });
  console.log(`  ✓ ${name}.png`);
}

async function waitReady(page, ms = 1200) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(ms);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  // ── 0. Landing page (DemoAuthBar NOT yet set) ─────────────────────────────
  console.log("\n── Landing & DemoAuthBar ──");
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000); // boot animation
  await shot(page, "00-landing");

  // ── Inject auth into localStorage ─────────────────────────────────────────
  await page.evaluate(
    ([tok, proj]) => {
      localStorage.setItem("aegis_token", tok);
      localStorage.setItem("aegis_project_id", proj);
    },
    [TOKEN, PROJECT_ID]
  );

  // ── 1. DemoAuthBar — amber state (navigate first to see it without token) ──
  // Open a fresh context to capture amber state
  const ctx2 = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page2 = await ctx2.newPage();
  await page2.goto(`${BASE}/console/rag`, { waitUntil: "networkidle" });
  await page2.waitForTimeout(800);
  await shot(page2, "01-demoauthbar-amber");
  await ctx2.close();

  // ── 2. Dashboard ──────────────────────────────────────────────────────────
  console.log("\n── Dashboard ──");
  await page.goto(`${BASE}/console`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "02-dashboard");
  // scroll to risk gauge area
  await page.evaluate(() => window.scrollTo(0, 300));
  await page.waitForTimeout(600);
  await shot(page, "03-dashboard-scrolled");

  // ── 3. DemoAuthBar — green state ──────────────────────────────────────────
  console.log("\n── DemoAuthBar green ──");
  await page.goto(`${BASE}/console/rag`, { waitUntil: "networkidle" });
  await waitReady(page, 600);
  await shot(page, "04-demoauthbar-green");

  // ── 4. RAG ────────────────────────────────────────────────────────────────
  console.log("\n── RAG Pipeline ──");
  await waitReady(page, 1000);
  await shot(page, "05-rag-idle");

  // After upload already done in smoke test, refresh to see document list
  await page.reload({ waitUntil: "networkidle" });
  await waitReady(page, 1200);
  await shot(page, "06-rag-with-document");

  // ── 5. Vision ─────────────────────────────────────────────────────────────
  console.log("\n── Vision ──");
  await page.goto(`${BASE}/console/vision`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "07-vision-idle");

  // ── 6. Agent ─────────────────────────────────────────────────────────────
  console.log("\n── Agent ──");
  await page.goto(`${BASE}/console/agent`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "08-agent-idle");

  // ── 7. Billing ───────────────────────────────────────────────────────────
  console.log("\n── Billing ──");
  await page.goto(`${BASE}/console/billing`, { waitUntil: "networkidle" });
  await waitReady(page, 1500);
  await shot(page, "09-billing");

  // ── 8. Observability ─────────────────────────────────────────────────────
  console.log("\n── Observability ──");
  await page.goto(`${BASE}/console/observability`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "10-observability");

  // ── 9. Security ──────────────────────────────────────────────────────────
  console.log("\n── Security ──");
  await page.goto(`${BASE}/console/security`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "11-security");

  // ── 10. SQL Airlock ───────────────────────────────────────────────────────
  console.log("\n── SQL Airlock ──");
  await page.goto(`${BASE}/console/airlock`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "12-airlock");

  // ── 11. Tenants ───────────────────────────────────────────────────────────
  console.log("\n── Tenants ──");
  await page.goto(`${BASE}/console/tenants`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "13-tenants");

  // ── 12. Settings ─────────────────────────────────────────────────────────
  console.log("\n── Settings ──");
  await page.goto(`${BASE}/console/settings`, { waitUntil: "networkidle" });
  await waitReady(page);
  await shot(page, "14-settings");

  await browser.close();

  const files = fs.readdirSync(OUT_DIR).filter((f) => f.endsWith(".png"));
  console.log(`\n✓ ${files.length} screenshots saved to docs/screenshots/`);
  files.forEach((f) => console.log(`  ${f}`));
})().catch((e) => {
  console.error("Screenshot script failed:", e.message);
  process.exit(1);
});
