// Converts a single HTML file to a print-styled PDF via headless Chromium (playwright-core,
// the system-installed Chrome — same pattern used throughout this repo's earlier productions,
// see CLAUDE.md §6 Batch A6/ISO Cert). No network access; `file://` load only.
//
// Usage: node render_pdf.mjs <input.html> <output.pdf>

import { chromium } from 'playwright-core';
import path from 'path';
import { pathToFileURL } from 'url';

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) {
  console.error('Usage: node render_pdf.mjs <input.html> <output.pdf>');
  process.exit(1);
}

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage();
await page.goto(pathToFileURL(path.resolve(inputPath)).href, { waitUntil: 'networkidle' });

await page.pdf({
  path: path.resolve(outputPath),
  format: 'A4',
  printBackground: true,
  preferCSSPageSize: true,
});

await browser.close();
console.log('wrote', outputPath);
