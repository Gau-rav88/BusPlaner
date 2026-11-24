/**
 * Automated Screenshot Capture Script for Milestone 11.1 DLM1 Frontend Validation.
 * Connects to http://127.0.0.1:3002 (backed by DLM1 on port 8001).
 * Captures:
 * 1. dlm1_main_planner.png: Main planner view showing CURRENT_VERIFIED timetable status and live vehicles.
 * 2. dlm1_stop_search.png: Stop autocomplete showing DLM1 stops (Stop 284 Adarsh Nagar).
 * 3. dlm1_journey_results_road_geometry.png: Direct journey results with DLM1 road geometry polyline and badge.
 * 4. dlm1_transfer_journey.png: Transfer journey option on DLM1.
 * 5. dlm1_mobile_view.png: Mobile responsive layout (375x812) on DLM1.
 */

import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(ROOT_DIR, 'reports', 'screenshots');

async function run() {
  console.log('Launching headless Chrome for DLM1 frontend validation...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    const page = await browser.newPage();
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error('Browser console error:', msg.text());
      }
    });

    // 1. Main Planner Screen
    console.log('[1/5] Capturing dlm1_main_planner.png (1280x850)...');
    await page.setViewport({ width: 1280, height: 850, deviceScaleFactor: 2 });
    await page.goto('http://127.0.0.1:3002', { waitUntil: 'networkidle0' });
    await page.waitForSelector('header');
    await new Promise((r) => setTimeout(r, 1500));

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'dlm1_main_planner.png'),
      fullPage: false,
    });
    console.log('  Saved dlm1_main_planner.png');

    // 2. Stop Autocomplete Search
    console.log('[2/5] Testing stop autocomplete and capturing dlm1_stop_search.png...');
    // Focus Origin input and type 'Adarsh Nagar'
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length >= 1) {
      await inputs[0].click();
      await inputs[0].type('Adarsh Nagar', { delay: 50 });
      await new Promise((r) => setTimeout(r, 1000));

      // Wait for dropdown button with 'Select'
      await page.waitForSelector('button ::-p-text(Select)', { timeout: 8000 });
      await page.screenshot({
        path: path.join(SCREENSHOTS_DIR, 'dlm1_stop_search.png'),
        fullPage: false,
      });
      console.log('  Saved dlm1_stop_search.png');

      // Click the first stop result
      const selectButtons = await page.$$('button ::-p-text(Select)');
      if (selectButtons.length > 0) {
        await selectButtons[0].click();
      }
    }
    await new Promise((r) => setTimeout(r, 600));

    // Focus Destination input and type 'Mukarba'
    const updatedInputs = await page.$$('input[type="text"]');
    if (updatedInputs.length >= 2) {
      await updatedInputs[1].click();
      await updatedInputs[1].type('Mukarba', { delay: 50 });
      await new Promise((r) => setTimeout(r, 1000));

      const destSelectButtons = await page.$$('button ::-p-text(Select)');
      if (destSelectButtons.length > 0) {
        await destSelectButtons[0].click();
      }
    }
    await new Promise((r) => setTimeout(r, 600));

    // 3. Submit Journey Search for DLM1 corridor
    console.log('[3/5] Submitting journey search & capturing dlm1_journey_results_road_geometry.png...');
    const searchBtn = await page.waitForSelector('button ::-p-text(Search Bus Journeys)');
    if (searchBtn) {
      await searchBtn.click();
    }

    await page.waitForSelector('::-p-text(Available Journeys)', { timeout: 15000 });
    await new Promise((r) => setTimeout(r, 1500));

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'dlm1_journey_results_road_geometry.png'),
      fullPage: false,
    });
    console.log('  Saved dlm1_journey_results_road_geometry.png');

    // 4. Expand Step-by-Step Route Details
    console.log('[4/5] Expanding route details and capturing dlm1_expanded_details.png...');
    const expandBtn = await page.waitForSelector('button ::-p-text(View Step-by-Step Route)');
    if (expandBtn) {
      await expandBtn.click();
      await new Promise((r) => setTimeout(r, 800));
      await page.screenshot({
        path: path.join(SCREENSHOTS_DIR, 'dlm1_expanded_details.png'),
        fullPage: false,
      });
      console.log('  Saved dlm1_expanded_details.png');
    }

    // 5. Mobile Layout Viewport (375x812)
    console.log('[5/5] Resizing to mobile viewport (375x812) & capturing dlm1_mobile_view.png...');
    await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2, isMobile: true });
    await new Promise((r) => setTimeout(r, 800));

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'dlm1_mobile_view.png'),
      fullPage: false,
    });
    console.log('  Saved dlm1_mobile_view.png');

    console.log('\nAll DLM1 frontend validation screenshots captured successfully!');
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error('Screenshot run failed:', err);
  process.exit(1);
});
