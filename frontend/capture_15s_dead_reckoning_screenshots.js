import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACTS_DIR = '/Users/gauravchauhan/.gemini/antigravity/brain/fe981391-7b71-4c56-8179-7c5bb53c4171';

async function run() {
  console.log('Launching Puppeteer for Dead Reckoning & GPS Correction validation...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 900, deviceScaleFactor: 2 });

    console.log('Navigating to http://localhost:3000...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));

    // Fill in Origin: Adarsh Nagar and Destination: Mukarba Chowk
    console.log('Typing Origin: Adarsh Nagar...');
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length >= 2) {
      await inputs[0].click({ clickCount: 3 });
      await inputs[0].type('Adarsh Nagar', { delay: 30 });
      await new Promise((r) => setTimeout(r, 1200));

      const selectBtns1 = await page.$$('button');
      for (const b of selectBtns1) {
        const text = await page.evaluate(el => el.textContent, b);
        if (text && text.includes('Select')) {
          await b.click();
          break;
        }
      }
      await new Promise((r) => setTimeout(r, 800));

      console.log('Typing Destination: Mukarba Chowk...');
      const inputs2 = await page.$$('input[type="text"]');
      await inputs2[1].click({ clickCount: 3 });
      await inputs2[1].type('Mukarba Chowk', { delay: 30 });
      await new Promise((r) => setTimeout(r, 1200));

      const selectBtns2 = await page.$$('button');
      for (const b of selectBtns2) {
        const text = await page.evaluate(el => el.textContent, b);
        if (text && text.includes('Select')) {
          await b.click();
          break;
        }
      }
      await new Promise((r) => setTimeout(r, 800));
    }

    // Set Departure Time to 21:30:00
    const timeInput = await page.$('input[type="time"]');
    if (timeInput) {
      await timeInput.click({ clickCount: 3 });
      await timeInput.type('21:30:00');
      await new Promise((r) => setTimeout(r, 500));
    }

    // Submit journey planning form
    console.log('Submitting Search Bus Journeys...');
    const submitBtn = await page.$('button[type="submit"]');
    if (submitBtn) {
      await submitBtn.click();
    }
    await new Promise((r) => setTimeout(r, 3500));

    // Select the first journey alternative card
    console.log('Selecting journey card...');
    const journeyCards = await page.$$('div[class*="cursor-pointer"]');
    if (journeyCards.length > 0) {
      await journeyCards[0].click();
      console.log('Selected Journey Option 1');
    }

    // Wait for Mode B to engage and fetch suitable buses (15s priority polling)
    console.log('Waiting for Mode B suitable buses to render on map...');
    await new Promise((r) => setTimeout(r, 4000));

    // Screenshot 33: Mode B with verified suitable buses along route shape
    const screenshot33Path = path.join(ARTIFACTS_DIR, '33_actual_15s_dead_reckoning_mode_b.png');
    await page.screenshot({ path: screenshot33Path, fullPage: false });
    console.log(`Saved screenshot 33 to ${screenshot33Path}`);

    // Click on the suitable bus marker to open its popup
    console.log('Clicking on suitable bus marker...');
    // Look for suitable pulsing halo or marker
    const suitableMarker = await page.$('.suitable-icon-inner, .bus-icon-inner, .leaflet-marker-icon.custom-map-marker');
    if (suitableMarker) {
      await suitableMarker.click();
      await new Promise((r) => setTimeout(r, 1500));
      console.log('Opened suitable bus popup');
    } else {
      console.log('Checking all markers...');
      const allMarkers = await page.$$('.leaflet-marker-icon');
      if (allMarkers.length > 0) {
        await allMarkers[allMarkers.length - 1].click();
        await new Promise((r) => setTimeout(r, 1500));
      }
    }

    // Screenshot 34: Popup details with route progress, drift error, calculation times
    const screenshot34Path = path.join(ARTIFACTS_DIR, '34_dead_reckoned_popup_and_drift_telemetry.png');
    await page.screenshot({ path: screenshot34Path, fullPage: false });
    console.log(`Saved screenshot 34 to ${screenshot34Path}`);

    console.log('Screenshots captured successfully!');
  } catch (err) {
    console.error('Puppeteer execution error:', err);
  } finally {
    await browser.close();
  }
}

run();
