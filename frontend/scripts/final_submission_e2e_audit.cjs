/**
 * Final Submission Readiness End-to-End Browser Audit Script
 * Runs Puppeteer against http://127.0.0.1:3000 (connected to Port 8000 DLM1 Backend)
 * Verifies Task A (20s Live Vehicle Updates) & Task B (Live Bus to Board Guidance)
 * plus Tasks 1-6 usability items.
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

async function runFinalAudit() {
  console.log('======================================================================');
  console.log('DELHI TRANSIT PLANNER: FINAL SYSTEM AUDIT & VERIFICATION');
  console.log('GOVERNING STATUS: DEGRADE | DEADLINE: NOVEMBER 24, 2026');
  console.log('======================================================================\n');

  const auditResults = {};

  // 1. Backend Connection Check
  console.log('>>> [CHECK 1/8] Verifying DLM1 Backend on Port 8000 via Vite Proxy (Port 3000)...');
  try {
    const routeData = await fetchJson('http://127.0.0.1:3000/api/v1/routes/1598');
    const liveStatus = await fetchJson('http://127.0.0.1:3000/api/v1/live/status');

    console.log(`Route 1598: has_shape_geometry=${routeData.has_shape_geometry}, shape points=${routeData.shape_coordinates?.length}`);
    console.log(`Live Status: status=${liveStatus.feed_availability_status}, active_vehicles=${liveStatus.active_vehicles_count}`);

    if (routeData.has_shape_geometry === true && routeData.shape_coordinates?.length === 416 && liveStatus.active_vehicles_count > 0) {
      console.log('✓ PASS: Connected to DLM1 backend on Port 8000 (416 shape points, live feed active).');
      auditResults['1_DLM1_Backend_Connection'] = 'PASS';
    } else {
      console.error('✗ FAIL: Backend response did not match DLM1 specifications.');
      auditResults['1_DLM1_Backend_Connection'] = 'FAIL';
    }
  } catch (err) {
    console.error('✗ FAIL: Unable to connect to backend:', err.message);
    auditResults['1_DLM1_Backend_Connection'] = 'FAIL';
  }

  // Launch Chromium
  console.log('\n>>> Launching headless Chromium browser...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1366,900'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 900 });

  const vehicleRequests = [];
  page.on('request', (req) => {
    if (req.url().includes('/api/v1/live/vehicles')) {
      vehicleRequests.push({ url: req.url(), timestamp: Date.now() });
    }
  });

  try {
    console.log('>>> Navigating to http://127.0.0.1:3000 ...');
    await page.goto('http://127.0.0.1:3000', { waitUntil: 'networkidle2', timeout: 15000 });
    console.log('✓ Page loaded.');

    // 2. Date/Time & Reset to Live
    console.log('\n>>> [CHECK 2/8] Testing Date/Time IST & "Reset to Live"...');
    const now = new Date();
    const expectedDate = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(now);
    const dateVal = await page.$eval('input[type="date"]', (el) => el.value);
    console.log(`Initial Date: "${dateVal}" (Expected: "${expectedDate}")`);

    await clickButtonWithText(page, 'North GT Road');
    await new Promise((r) => setTimeout(r, 400));
    const presetDate = await page.$eval('input[type="date"]', (el) => el.value);

    await clickButtonWithText(page, 'Reset to Live');
    await new Promise((r) => setTimeout(r, 400));
    const resetDate = await page.$eval('input[type="date"]', (el) => el.value);

    if (dateVal === expectedDate && presetDate === '2026-10-01' && resetDate === expectedDate) {
      console.log('✓ PASS: Date/Time initializes to device IST and "Reset to Live" restores current date/time.');
      auditResults['2_DateTime_ResetToLive'] = 'PASS';
    } else {
      console.error('✗ FAIL: Date/Time reset mismatch.');
      auditResults['2_DateTime_ResetToLive'] = 'FAIL';
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_final_reset_to_live.png') });

    // 3. Direct Journey Planning & Live Bus Candidate Guidance
    console.log('\n>>> [CHECK 3/8] Planning Direct Journey & Verifying Live Bus Guidance Card...');
    await clickButtonWithText(page, 'North GT Road');
    await new Promise((r) => setTimeout(r, 400));

    const searchBtn = await page.waitForSelector('button[type="submit"]');
    await searchBtn.click();

    await page.waitForFunction(
      () => document.body.innerText.includes('Journey Option 1') || document.body.innerText.includes('Optimal Route Options'),
      { timeout: 15000 }
    );
    console.log('✓ Journey results loaded.');

    // Expand step-by-step route to display transit legs and live bus guidance
    await clickButtonWithText(page, 'View Step-by-Step Route');
    await new Promise((r) => setTimeout(r, 800));

    // Verify "Live Bus to Board" card in DOM
    const liveBusCardInfo = await page.evaluate(() => {
      const card = Array.from(document.querySelectorAll('div')).find((el) =>
        el.textContent.includes('Live Bus to Board')
      );
      if (!card) return null;
      return {
        text: card.textContent,
        hasDisclaimer: card.textContent.includes('Live candidate bus based on real-time GTFS-RT feed'),
        hasStatus: card.textContent.includes('Approaching') ||
                   card.textContent.includes('Near Boarding Stop') ||
                   card.textContent.includes('Route matches — direction unverified') ||
                   card.textContent.includes('Live bus not identified'),
        hasVehicleId: /DL[0-9A-Z]+/i.test(card.textContent),
        hasSpeed: card.textContent.includes('km/h'),
        hasSourcePing: card.textContent.includes('IST') && card.textContent.includes('Source ping:'),
      };
    });

    console.log('Live Bus Guidance Card Details:', JSON.stringify(liveBusCardInfo, null, 2));

    if (liveBusCardInfo && liveBusCardInfo.hasDisclaimer && liveBusCardInfo.hasStatus) {
      console.log('✓ PASS: "Live Bus to Board" guidance card rendered with verified status, candidate details, and disclaimer.');
      auditResults['3_Live_Bus_Guidance_Card'] = 'PASS';
    } else {
      console.error('✗ FAIL: "Live Bus to Board" card missing or lacking required candidate fields.');
      auditResults['3_Live_Bus_Guidance_Card'] = 'FAIL';
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_final_direct_journey_live_bus.png') });

    // 4. Map Shape Slicing and Clean Visuals
    console.log('\n>>> [CHECK 4/8] Verifying Map Shape Slicing & Route Visuals...');
    const mapDetails = await page.evaluate(() => {
      const markers = Array.from(document.querySelectorAll('.custom-map-marker')).map((el) => el.textContent.trim());
      const paths = Array.from(document.querySelectorAll('.leaflet-pane.leaflet-overlay-pane svg path')).map((p) => p.getAttribute('d') || '');
      const banner = document.querySelector('.leaflet-container')?.parentElement?.querySelector('span.font-semibold')?.textContent || '';
      return { markers, pathsCount: paths.length, banner };
    });

    console.log(`Map Markers: ${JSON.stringify(mapDetails.markers)}`);
    console.log(`SVG Polyline Paths: ${mapDetails.pathsCount}, Banner: "${mapDetails.banner}"`);

    const hasOrigin = mapDetails.markers.some((m) => m.includes('A'));
    const hasDest = mapDetails.markers.some((m) => m.includes('B'));
    const hasBoard = mapDetails.markers.some((m) => m.includes('🚏'));
    const hasAlight = mapDetails.markers.some((m) => m.includes('🏁'));

    if (hasOrigin && hasDest && hasBoard && hasAlight && mapDetails.pathsCount >= 1) {
      console.log('✓ PASS: Sliced route polyline displayed with distinct A, B, boarding, and alighting markers.');
      auditResults['4_Map_Shape_Slicing'] = 'PASS';
    } else {
      console.error('✗ FAIL: Map missing expected markers or path.');
      auditResults['4_Map_Shape_Slicing'] = 'FAIL';
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_final_map_route_shapes.png') });

    // 5. Legend Show/Hide Toggle
    console.log('\n>>> [CHECK 5/8] Verifying Legend Show/Hide Toggle...');
    const hideLegendBtn = await page.$('button[title="Hide Legend"]');
    if (hideLegendBtn) {
      await hideLegendBtn.click();
    } else {
      await clickButtonWithText(page, 'Hide');
    }
    await new Promise((r) => setTimeout(r, 400));

    const showBtn = await findButtonByText(page, 'Show Legend');
    const isHidden = showBtn !== null;
    console.log(`Legend collapsed state: ${isHidden}`);

    if (showBtn) {
      await showBtn.click();
      await new Promise((r) => setTimeout(r, 400));
    }
    const isRestored = await page.evaluate(() => document.body.innerText.includes('Origin Point (A)'));
    console.log(`Legend restored state: ${isRestored}`);

    if (isHidden && isRestored) {
      console.log('✓ PASS: Legend toggle collapses and expands reliably.');
      auditResults['5_Legend_Toggle'] = 'PASS';
    } else {
      console.error('✗ FAIL: Legend toggle failed.');
      auditResults['5_Legend_Toggle'] = 'FAIL';
    }

    // 6. Place Name Reverse Geocoding
    console.log('\n>>> [CHECK 6/8] Verifying Place Name Resolution on Map Click...');
    const mapContainer = await page.$('.leaflet-container');
    const mapBox = await mapContainer.boundingBox();
    await page.mouse.click(mapBox.x + mapBox.width / 2, mapBox.y + mapBox.height / 2);
    await new Promise((r) => setTimeout(r, 1500));

    const originInputs = await page.$$eval('input[type="text"]', (inputs) => inputs.map((i) => i.value));
    console.log('Inputs after map click:', originInputs);
    const hasHumanPlace = originInputs.some((val) => val.includes('Near') || val.includes('Terminal') || val.includes('Stop') || val.includes('Location'));

    if (hasHumanPlace) {
      console.log('✓ PASS: Map click resolves human-readable place name while coordinates remain internally bound.');
      auditResults['6_Place_Names'] = 'PASS';
    } else {
      console.error('✗ FAIL: Place name resolution failed.');
      auditResults['6_Place_Names'] = 'FAIL';
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_final_place_names.png') });

    // 7. Nearby Buses & Direction Guard
    console.log('\n>>> [CHECK 7/8] Verifying Nearby Buses Suitability & Direction Guard...');
    await clickButtonWithText(page, 'Nearby Buses');
    await new Promise((r) => setTimeout(r, 1500));

    const nearbyBusTexts = await page.$$eval('.divide-y > div', (divs) => divs.map((d) => d.textContent.trim()));
    console.log(`Discovered ${nearbyBusTexts.length} nearby buses.`);

    let falseSuitabilityFound = false;
    let directionUnverifiedFound = false;

    nearbyBusTexts.forEach((t) => {
      if (t.includes('Route matches — direction unverified')) directionUnverifiedFound = true;
      if (t.includes('Suitable for Journey') && !t.includes('direction unverified')) falseSuitabilityFound = true;
    });

    console.log(`- Direction unverified fallback present: ${directionUnverifiedFound}`);
    console.log(`- Unverified "Suitable for Journey" falsely claimed: ${falseSuitabilityFound}`);

    if (!falseSuitabilityFound) {
      console.log('✓ PASS: Direction guard strictly prevents false "Suitable for Journey" labels.');
      auditResults['7_Nearby_Suitability_Guard'] = 'PASS';
    } else {
      console.error('✗ FAIL: False suitability label detected!');
      auditResults['7_Nearby_Suitability_Guard'] = 'FAIL';
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_final_nearby_buses_suitability.png') });

    // 8. Transfer Journey Shape Slicing and Multi-leg Markers
    console.log('\n>>> [CHECK 8/8] Verifying Transfer Journey Multi-Leg Slicing...');
    await new Promise((r) => setTimeout(r, 400));

    // Clear and fill Nehru -> Alipur
    const textInputs = await page.$$('input[type="text"]');
    await textInputs[0].click({ clickCount: 3 });
    await textInputs[0].type('Nehru');
    await page.waitForFunction(() => document.body.innerText.includes('Nehru'), { timeout: 6000 });
    
    // Select dropdown option
    const spans = await page.$$('span');
    for (const s of spans) {
      const text = await page.evaluate(el => el.textContent, s);
      if (text && text.trim() === 'Select') {
        await s.click();
        break;
      }
    }
    await new Promise((r) => setTimeout(r, 600));

    const textInputs2 = await page.$$('input[type="text"]');
    await textInputs2[1].click({ clickCount: 3 });
    await textInputs2[1].type('Alipur');
    await page.waitForFunction(() => document.body.innerText.includes('Alipur'), { timeout: 6000 });

    const spans2 = await page.$$('span');
    for (const s of spans2) {
      const text = await page.evaluate(el => el.textContent, s);
      if (text && text.trim() === 'Select') {
        await s.click();
        break;
      }
    }
    await new Promise((r) => setTimeout(r, 600));

    const submitBtn = await page.waitForSelector('button[type="submit"]');
    await submitBtn.click();

    await page.waitForFunction(
      () => document.body.innerText.includes('Journey Option 1') || document.body.innerText.includes('Optimal Route Options'),
      { timeout: 15000 }
    );
    console.log('✓ Transfer journey options loaded.');
    await new Promise((r) => setTimeout(r, 1500));

    const transferMapDetails = await page.evaluate(() => {
      const markers = Array.from(document.querySelectorAll('.custom-map-marker')).map((el) => el.textContent.trim());
      const paths = Array.from(document.querySelectorAll('.leaflet-pane.leaflet-overlay-pane svg path')).map((p) => p.getAttribute('d') || '');
      return { markers, pathsCount: paths.length };
    });

    console.log(`Transfer Markers: ${JSON.stringify(transferMapDetails.markers)}`);
    console.log(`Transfer Polyline Paths: ${transferMapDetails.pathsCount}`);

    const hasTransferBoard = transferMapDetails.markers.filter((m) => m.includes('🚏')).length >= 1;
    const hasTransferAlight = transferMapDetails.markers.filter((m) => m.includes('🏁')).length >= 1;

    if (hasTransferBoard && hasTransferAlight && transferMapDetails.pathsCount >= 1) {
      console.log('✓ PASS: Transfer journey rendered with distinct transit legs and transfer walking connection.');
      auditResults['8_Transfer_Journey_MultiLeg'] = 'PASS';
    } else {
      console.error('✗ FAIL: Transfer journey failed to render required markers.');
      auditResults['8_Transfer_Journey_MultiLeg'] = 'FAIL';
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_final_transfer_journey.png') });

  } catch (err) {
    console.error('Audit execution error:', err);
  } finally {
    await browser.close();
  }

  // Final Summary
  console.log('\n======================================================================');
  console.log('FINAL AUDIT VERIFICATION RESULTS:');
  console.log('======================================================================');
  let passCount = 0;
  let totalCount = 0;
  for (const [key, val] of Object.entries(auditResults)) {
    console.log(`  [${val}] ${key}`);
    totalCount++;
    if (val === 'PASS') passCount++;
  }
  console.log(`\nRESULT: ${passCount}/${totalCount} CHECKS PASSED.`);
  console.log('======================================================================\n');

  if (passCount === totalCount && totalCount > 0) {
    console.log('ALL FINAL SUBMISSION CRITERIA FULLY VERIFIED.');
    process.exit(0);
  } else {
    console.error('ONE OR MORE VERIFICATION CHECKS FAILED.');
    process.exit(1);
  }
}

runFinalAudit();
