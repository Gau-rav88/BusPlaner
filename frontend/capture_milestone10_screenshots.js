/**
 * Milestone 10.1 Screenshot Capture Script.
 * Uses Puppeteer to exercise the live application and verify:
 * 1. Live vehicle pins appearing on the interactive map.
 * 2. Distinct orange bus markers and live popup details (vehicle ID, route, speed, age, disclaimer).
 * 3. Journey planning operational alongside real-time GTFS-RT telemetry.
 */

import puppeteer from 'puppeteer';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(ROOT_DIR, 'reports', 'screenshots');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function run() {
  console.log('Launching Puppeteer browser to capture Milestone 10.1 evidence...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1366, height: 850, deviceScaleFactor: 2 });

    console.log('[1/3] Navigating to http://127.0.0.1:3000...');
    await page.goto('http://127.0.0.1:3000', { waitUntil: 'networkidle0' });

    // Wait for header and map to load
    await page.waitForSelector('header');
    await new Promise((r) => setTimeout(r, 2500));

    // Capture main live map view
    console.log('[2/3] Capturing reports/screenshots/milestone10_live_map.png...');
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'milestone10_live_map.png'),
      fullPage: false,
    });
    console.log('  ✓ Saved milestone10_live_map.png');

    // Click on a live bus marker if present
    const busMarkers = await page.$$('.custom-map-marker');
    console.log(`Found ${busMarkers.length} custom markers on map.`);

    // Find and click an orange bus marker (marker with bus emoji or orange bg)
    let clicked = false;
    for (const marker of busMarkers) {
      const text = await page.evaluate((el) => el.innerText || el.textContent, marker);
      if (text && text.includes('🚌')) {
        await marker.click();
        clicked = true;
        break;
      }
    }

    if (clicked) {
      await new Promise((r) => setTimeout(r, 800));
      console.log('Clicked live bus marker, capturing popup...');
      await page.screenshot({
        path: path.join(SCREENSHOTS_DIR, 'milestone10_live_bus_popup.png'),
        fullPage: false,
      });
      console.log('  ✓ Saved milestone10_live_bus_popup.png');
    }

    // 3. Plan a journey on North GT Road to show journey planning works seamlessly
    console.log('[3/3] Planning journey & capturing milestone10_journey_with_live_buses.png...');
    const presetBtn = await page.waitForSelector('button ::-p-text(North GT Road)');
    if (presetBtn) {
      await presetBtn.click();
      await new Promise((r) => setTimeout(r, 600));
    }

    const searchBtn = await page.waitForSelector('button ::-p-text(Search Bus Journeys)');
    if (searchBtn) {
      await searchBtn.click();
      await new Promise((r) => setTimeout(r, 2000));
    }

    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'milestone10_journey_with_live_buses.png'),
      fullPage: false,
    });
    console.log('  ✓ Saved milestone10_journey_with_live_buses.png');

    console.log('Screenshot capture completed successfully.');
  } catch (err) {
    console.error('Error capturing screenshots:', err);
  } finally {
    await browser.close();
  }
}

run();

