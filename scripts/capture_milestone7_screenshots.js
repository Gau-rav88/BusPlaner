/**
 * Automated Screenshot Capture Script for Milestone 7 Frontend.
 * Uses Puppeteer to exercise the UI and capture:
 * 1. Main planner screen (desktop).
 * 2. Journey alternatives comparison screen.
 * 3. Expanded step-by-step route details screen.
 * 4. Responsive mobile layout screen.
 */

import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(ROOT_DIR, 'reports', 'screenshots');

async function captureScreenshots() {
  console.log('Launching headless browser for Milestone 7 screenshot capture...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    const page = await browser.newPage();

    // 1. Desktop: Main Planner View
    console.log('[1/4] Capturing main_planner.png (1280x850)...');
    await page.setViewport({ width: 1280, height: 850, deviceScaleFactor: 2 });
    await page.goto('http://127.0.0.1:3000', { waitUntil: 'networkidle0' });

    // Wait for health check to complete
    await page.waitForSelector('header');
    await new Promise((r) => setTimeout(r, 1000));
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'main_planner.png'),
      fullPage: false,
    });
    console.log('  Saved reports/screenshots/main_planner.png');

    // 2. Click Preset & Submit Journey Search
    console.log('[2/4] Triggering North GT Road query & capturing journey_results.png...');
    // Click the North GT Road preset button
    const presetBtn = await page.waitForSelector('button ::-p-text(North GT Road)');
    if (presetBtn) {
      await presetBtn.click();
    }
    await new Promise((r) => setTimeout(r, 500));

    // Click Search Bus Journeys button
    const searchBtn = await page.waitForSelector('button ::-p-text(Search Bus Journeys)');
    if (searchBtn) {
      await searchBtn.click();
    }

    // Wait for journey results to render
    await page.waitForSelector('::-p-text(Available Journeys)', { timeout: 15000 });
    await new Promise((r) => setTimeout(r, 1000));

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'journey_results.png'),
      fullPage: false,
    });
    console.log('  Saved reports/screenshots/journey_results.png');

    // 3. Expand Details on First Alternative
    console.log('[3/4] Expanding route steps & capturing expanded_journey_details.png...');
    const expandBtn = await page.waitForSelector('button ::-p-text(View Step-by-Step Route)');
    if (expandBtn) {
      await expandBtn.click();
    }
    await new Promise((r) => setTimeout(r, 800));

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'expanded_journey_details.png'),
      fullPage: false,
    });
    console.log('  Saved reports/screenshots/expanded_journey_details.png');

    // 4. Mobile Layout
    console.log('[4/4] Resizing to mobile viewport (375x812) & capturing mobile_layout.png...');
    await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2, isMobile: true });
    await new Promise((r) => setTimeout(r, 800));

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'mobile_layout.png'),
      fullPage: false,
    });
    console.log('  Saved reports/screenshots/mobile_layout.png');

    console.log('\nAll 4 screenshots captured successfully!');
  } finally {
    await browser.close();
  }
}

captureScreenshots().catch((err) => {
  console.error('Screenshot capture failed:', err);
  process.exit(1);
});

