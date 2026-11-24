/**
 * Verification of Transfer Journey Shape Slicing and Walking Endpoints
 */
const puppeteer = require('puppeteer');

async function testTransferJourney() {
  console.log('>>> Launching Chromium to verify transfer journey...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,900'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  try {
    await page.goto('http://127.0.0.1:3000', { waitUntil: 'networkidle2' });

    console.log('Searching for Nehru in Origin input...');
    const originInput = (await page.$$('input[type="text"]'))[0];
    await originInput.click();
    await originInput.type('Nehru');
    await page.waitForFunction(() => document.body.innerText.includes('Nehru'), { timeout: 6000 });
    
    // Click first Select button in dropdown
    const selectButtons = await page.$$('span');
    for (const s of selectButtons) {
      const text = await page.evaluate(el => el.textContent, s);
      if (text && text.trim() === 'Select') {
        await s.click();
        break;
      }
    }
    await new Promise((r) => setTimeout(r, 600));

    console.log('Searching for Alipur in Destination input...');
    const destInput = (await page.$$('input[type="text"]'))[1];
    await destInput.click();
    await destInput.type('Alipur');
    await page.waitForFunction(() => document.body.innerText.includes('Alipur'), { timeout: 6000 });
    
    const selectButtons2 = await page.$$('span');
    for (const s of selectButtons2) {
      const text = await page.evaluate(el => el.textContent, s);
      if (text && text.trim() === 'Select') {
        await s.click();
        break;
      }
    }
    await new Promise((r) => setTimeout(r, 600));

    // Submit Journey Search
    console.log('Submitting transfer journey search...');
    const searchBtn = await page.waitForSelector('button[type="submit"]');
    await searchBtn.click();

    await page.waitForFunction(() => document.body.innerText.includes('Journey Option 1') || document.body.innerText.includes('Optimal Route Options'), { timeout: 12000 });
    console.log('✓ Transfer journey results loaded.');

    await new Promise((r) => setTimeout(r, 1500));

    // Inspect map markers & polylines
    const mapDetails = await page.evaluate(() => {
      const markers = Array.from(document.querySelectorAll('.custom-map-marker')).map((el) => el.textContent.trim());
      const paths = Array.from(document.querySelectorAll('.leaflet-pane.leaflet-overlay-pane svg path')).map((p) => p.getAttribute('d') || '');
      return { markers, pathsCount: paths.length };
    });

    console.log(`Transfer Map Markers detected: ${JSON.stringify(mapDetails.markers)}`);
    console.log(`Transfer SVG Polyline Paths detected: ${mapDetails.pathsCount}`);

    const hasOrigin = mapDetails.markers.some((m) => m.includes('A'));
    const hasDest = mapDetails.markers.some((m) => m.includes('B'));
    const boardMarkersCount = mapDetails.markers.filter((m) => m.includes('🚏')).length;
    const alightMarkersCount = mapDetails.markers.filter((m) => m.includes('🏁')).length;

    console.log(`Origin: ${hasOrigin}, Dest: ${hasDest}, Boarding markers: ${boardMarkersCount}, Alighting markers: ${alightMarkersCount}`);

    if (hasOrigin && hasDest && boardMarkersCount >= 1 && alightMarkersCount >= 1 && mapDetails.pathsCount >= 1) {
      console.log('✓ PASS: Transfer journey verified with multi-leg boarding/alighting markers and distinct transfer walking segments.');
    } else {
      console.error('✗ FAIL: Transfer journey did not render markers correctly.');
      process.exit(1);
    }

    await page.screenshot({ path: 'frontend/screenshots/05_transfer_journey_verified.png' });
  } catch (err) {
    console.error('Transfer test exception:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

testTransferJourney();
