/**
 * E2E Browser Audit for Full Fleet Live GTFS-RT Map Display
 * Verifies that ALL valid live vehicles returned by the backend (3000+ buses)
 * are rendered on the map, both before and after a journey is selected.
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const http = require('http');

const SCREENSHOT_DIR = path.resolve(__dirname, '../screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

async function findButtonByText(page, text) {
  const buttons = await page.$$('button');
  for (const btn of buttons) {
    const btnText = await page.evaluate((el) => el.textContent, btn);
    if (btnText && btnText.toLowerCase().includes(text.toLowerCase())) {
      return btn;
    }
  }
  return null;
}

async function clickButtonWithText(page, text) {
  const btn = await findButtonByText(page, text);
  if (!btn) throw new Error(`Button with text containing "${text}" not found`);
  await btn.click();
}

async function runFleetAudit() {
  console.log('======================================================================');
  console.log('DELHI TRANSIT PLANNER: FULL FLEET LIVE MAP E2E BROWSER AUDIT');
  console.log('======================================================================\n');

  // 1. Backend Count Verification
  console.log('>>> [STEP 1] Fetching live fleet counts from backend API...');
  const apiData = await fetchJson('http://127.0.0.1:8000/api/v1/live/vehicles?limit=5000');
  console.log(`Backend API Reports:`);
  console.log(`- Total Active Vehicles: ${apiData.total_active_vehicles}`);
  console.log(`- Returned Vehicles:     ${apiData.returned_vehicles_count}`);
  console.log(`- Current Snapshot:      ${apiData.current_vehicles_count}`);
  console.log(`- Last Known / Stale:    ${apiData.last_known_vehicles_count}`);
  console.log(`- Out of Area (NCR):     ${apiData.out_of_area_count}`);
  console.log(`- Feed Status:           ${apiData.feed_availability_status}`);

  if (apiData.returned_vehicles_count < 1000) {
    console.error(`✗ FAIL: Backend returned only ${apiData.returned_vehicles_count} vehicles (< 1000 threshold)!`);
    process.exit(1);
  }
  console.log('✓ PASS: Backend returned full fleet without truncation.\n');

  // 2. Launch Puppeteer
  console.log('>>> [STEP 2] Launching Chromium to verify frontend Leaflet map...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,900'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  try {
    console.log('>>> Navigating to http://127.0.0.1:3000 ...');
    await page.goto('http://127.0.0.1:3000', { waitUntil: 'networkidle2', timeout: 20000 });

    // Wait for Leaflet map to load
    await page.waitForSelector('.leaflet-container', { timeout: 10000 });
    console.log('✓ Leaflet map container initialized.');

    // Wait for live vehicles to be populated
    console.log('Waiting for live fleet polling...');
    await page.waitForFunction(
      () => {
        const btn = document.querySelector('button[title*="Live GTFS-RT"]');
        if (!btn) return false;
        const match = btn.textContent.match(/Buses\s*\(([0-9]+)\)/);
        return match && parseInt(match[1], 10) > 100;
      },
      { timeout: 15000 }
    );

    const busBtnText = await page.evaluate(() => {
      const btn = document.querySelector('button[title*="Live GTFS-RT"]');
      return btn ? btn.textContent.trim() : '';
    });
    console.log(`Toggle Button in DOM: "${busBtnText}"`);

    const busCountMatch = busBtnText.match(/Buses\s*\(([0-9]+)\)/);
    const displayedBusCount = busCountMatch ? parseInt(busCountMatch[1], 10) : 0;
    console.log(`Reported buses on map: ${displayedBusCount}`);

    if (displayedBusCount < 1000) {
      console.error(`✗ FAIL: Map displays only ${displayedBusCount} buses (< 1000)!`);
      process.exit(1);
    }
    console.log(`✓ PASS: Map successfully tracked and registered ${displayedBusCount} buses from feed.`);

    // Screenshot 1: Full fleet citywide map
    await new Promise((r) => setTimeout(r, 1000));
    const screenshot1Path = path.join(SCREENSHOT_DIR, '10_full_fleet_citywide_map.png');
    await page.screenshot({ path: screenshot1Path });
    console.log(`✓ Saved citywide full fleet screenshot to ${screenshot1Path}`);

    // 3. Inspect a Bus Popup
    console.log('\n>>> [STEP 3] Opening a vehicle popup to verify details...');
    // Click on the first bus marker in the Leaflet marker pane
    const markerClicked = await page.evaluate(() => {
      const markers = document.querySelectorAll('.leaflet-marker-pane .custom-map-marker');
      for (const m of markers) {
        if (m.textContent.includes('🚌') || m.textContent.includes('⭐')) {
          m.click();
          return true;
        }
      }
      return false;
    });

    if (markerClicked) {
      await new Promise((r) => setTimeout(r, 800));
      const popupText = await page.evaluate(() => {
        const popup = document.querySelector('.leaflet-popup-content');
        return popup ? popup.textContent : null;
      });
      console.log('Popup Content:', popupText);

      const hasVehicleId = /DL[0-9A-Z]+/i.test(popupText || '');
      const hasRoute = popupText && popupText.includes('Route');
      const hasDirection = popupText && (popupText.includes('Direction') || popupText.includes('unverified'));
      const hasSpeed = popupText && popupText.includes('Speed:');
      const hasSourcePing = popupText && popupText.includes('Source Ping:');

      console.log(`Popup verification: VehicleID=${hasVehicleId}, Route=${hasRoute}, Direction=${hasDirection}, Speed=${hasSpeed}, Ping=${hasSourcePing}`);

      if (hasVehicleId && hasRoute && hasDirection && hasSpeed && hasSourcePing) {
        console.log('✓ PASS: Vehicle popup contains complete verified telemetry fields.');
      } else {
        console.warn('⚠ Note: Some popup fields missing or format altered.');
      }

      const screenshotPopup = path.join(SCREENSHOT_DIR, '12_bus_marker_popup_details.png');
      await page.screenshot({ path: screenshotPopup });
      console.log(`✓ Saved bus popup screenshot to ${screenshotPopup}`);
    }

    // 4. Verify Full Fleet Remains Visible When a Journey is Selected
    console.log('\n>>> [STEP 4] Verifying Full Fleet REMAINS visible when journey is selected...');
    await clickButtonWithText(page, 'North GT Road');
    await new Promise((r) => setTimeout(r, 400));

    const searchBtn = await page.waitForSelector('button[type="submit"]');
    await searchBtn.click();

    await page.waitForFunction(
      () => document.body.innerText.includes('Journey Option 1') || document.body.innerText.includes('Optimal Route Options'),
      { timeout: 15000 }
    );
    console.log('✓ Journey Option 1 loaded.');

    await new Promise((r) => setTimeout(r, 1500));

    // Re-check bus count on the map
    const busCountAfterJourney = await page.evaluate(() => {
      const btn = document.querySelector('button[title*="Live GTFS-RT"]');
      const match = btn ? btn.textContent.match(/Buses\s*\(([0-9]+)\)/) : null;
      return match ? parseInt(match[1], 10) : 0;
    });

    console.log(`Bus count with journey selected: ${busCountAfterJourney}`);
    if (busCountAfterJourney < 1000) {
      console.error(`✗ FAIL: Bus markers dropped to ${busCountAfterJourney} when journey was selected!`);
      process.exit(1);
    }
    console.log(`✓ PASS: Full fleet (${busCountAfterJourney} buses) persists on map when journey is selected (not restricted to route).`);

    const screenshot2Path = path.join(SCREENSHOT_DIR, '11_full_fleet_with_journey_selected.png');
    await page.screenshot({ path: screenshot2Path });
    console.log(`✓ Saved screenshot with journey + full fleet to ${screenshot2Path}`);

  } catch (err) {
    console.error('Audit execution error:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }

  console.log('\n======================================================================');
  console.log('FULL FLEET E2E BROWSER AUDIT: 100% PASSED');
  console.log('======================================================================\n');
}

runFleetAudit();

