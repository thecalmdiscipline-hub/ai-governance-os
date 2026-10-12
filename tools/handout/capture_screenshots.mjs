// Captures the handout's screenshot set from the live portal, logged in as the
// `atlas_demo_admin` demo tenant (organisation 5, "Atlas Demo B.V." — never org 4, never a
// real client). Writes PNGs plus manifest.json to --out.
//
// Usage:
//   TOKEN_FILE=/path/to/token/file node capture_screenshots.mjs --out <dir>
//
// The token is read from a local file (never a CLI argument, never printed, never logged) —
// mint it server-side (see the hand-off's "productiecontrole" section) and point TOKEN_FILE at
// it. This script never mints a token itself and only talks to the already-running portal at
// https://app.valqeron.com.

import { chromium } from 'playwright-core';
import { execSync } from 'child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { homedir } from 'os';
import path from 'path';

const PORTAL_URL = 'https://app.valqeron.com';
const VIEWPORT = { width: 1440, height: 900 };

const TAB_SHOTS = [
  ['home', 'Home', 'The Home tab: environment overview and recent activity.'],
  ['core', 'Core', 'The Core tab: the control layer under every workflow.'],
  ['products', 'Products', 'The Products tab: the workflows active in this environment.'],
  ['results', 'Results', 'The Results tab: outcomes of workflows that have run.'],
  ['documents', 'Documents', 'The Documents tab: upload and ask questions about your documents.'],
  ['governance', 'Governance', "The Governance tab: policy, AI systems, risks, incidents, corrective actions and evidence."],
  ['account', 'Account', 'The Account tab: password, two-step verification and support requests.'],
];

const FICTIONAL_QUESTION = 'What does our onboarding checklist say about data handling?';

function frontendHeadSha() {
  const repo = path.join(homedir(), 'ai-governance-frontend');
  if (!existsSync(repo)) return 'unknown';
  try {
    return execSync('git log -1 --format=%h', { cwd: repo }).toString().trim() || 'unknown';
  } catch {
    return 'unknown';
  }
}

function parseArgs() {
  const args = process.argv.slice(2);
  const outIdx = args.indexOf('--out');
  if (outIdx === -1 || !args[outIdx + 1]) {
    console.error('Usage: node capture_screenshots.mjs --out <dir>');
    process.exit(2);
  }
  return { out: args[outIdx + 1] };
}

async function main() {
  const { out } = parseArgs();
  const tokenFile = process.env.TOKEN_FILE;
  if (!tokenFile) {
    console.error('Set TOKEN_FILE to a local file containing the session token.');
    process.exit(2);
  }
  const token = readFileSync(tokenFile, 'utf-8').trim();
  if (!token) {
    console.error(`${tokenFile} is empty.`);
    process.exit(2);
  }

  mkdirSync(out, { recursive: true });

  const consoleErrors = [];
  const failedRequests = [];

  const browser = await chromium.launch({ channel: 'chrome' });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('requestfailed', (req) => failedRequests.push(req.url()));

  await page.goto(PORTAL_URL, { waitUntil: 'domcontentloaded' });
  await page.evaluate((t) => localStorage.setItem('token', t), token);
  await page.reload({ waitUntil: 'networkidle' });

  const manifest = {
    _meta: {
      frontend_build_sha: frontendHeadSha(),
      captured_at: new Date().toISOString(),
      viewport: VIEWPORT,
      tenant: 'Atlas Demo B.V. (organisation 5, fictitious)',
    },
  };

  async function clickTab(label) {
    await page.locator('aside button', { hasText: label }).first().click();
    await page.waitForTimeout(700);
  }

  for (const [key, label, caption] of TAB_SHOTS) {
    await clickTab(label);
    const shotPath = path.join(out, `${key}.png`);
    await page.screenshot({ path: shotPath });
    manifest[key] = [{ path: path.basename(shotPath), caption }];
    console.log('captured', key);
  }

  // document_intelligence: the "Ask your documents" result state — the one module with a
  // start form reachable from the live tab navigation (see CLAUDE.md / A6's has_start_form
  // Fase-0 finding).
  await clickTab('Documents');
  await page.getByPlaceholder('Ask a question about your documents').fill(FICTIONAL_QUESTION);
  await page.getByRole('button', { name: /Ask documents|Processing/ }).click();
  await page.waitForTimeout(6000); // a real workflow run against OpenAI
  const dkShotPath = path.join(out, 'document_intelligence_1.png');
  await page.screenshot({ path: dkShotPath });
  manifest.document_intelligence = [
    { path: path.basename(dkShotPath), caption: 'Document Knowledge: asking a question and reviewing the answer.' },
  ];
  console.log('captured document_intelligence_1');

  await context.clearCookies();
  await page.evaluate(() => localStorage.clear());
  await browser.close();

  const manifestPath = path.join(out, 'manifest.json');
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log('wrote', manifestPath);

  if (consoleErrors.length) {
    console.log(`WARNING: ${consoleErrors.length} browser console error(s) during capture:`);
    consoleErrors.slice(0, 10).forEach((e) => console.log('  -', e));
  }
  if (failedRequests.length) {
    console.log(`WARNING: ${failedRequests.length} failed request(s) during capture:`);
    failedRequests.slice(0, 10).forEach((u) => console.log('  -', u));
  }
  if (!consoleErrors.length && !failedRequests.length) {
    console.log('No console errors, no failed requests during capture.');
  }
}

main();
