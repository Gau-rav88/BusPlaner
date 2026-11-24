import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACTS_DIR = '/Users/gauravchauhan/.gemini/antigravity/brain/fe981391-7b71-4c56-8179-7c5bb53c4171';

async function run() {
  console.log('Launching Puppeteer for Transit App Redesign capture...');
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

    console.log('Navigating to http://localhost:3000...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));

    // Screenshot 1: Clean Initial View
    console.log('Capturing Screenshot 1: Clean Initial View...');
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, '37_transit_app_redesign_initial_clean_view.png'),
      fullPage: false,
    });

    // Click Quick demo preset: North GT Road (Route 1598)
    console.log('Clicking Quick demo preset...');
    const presetBtn = await page.evaluateHandle(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      return btns.find(b => b.textContent && b.textContent.includes('North GT Road Corridor'));
    });
    if (presetBtn && presetBtn.asElement()) {
      await presetBtn.asElement().click();
      await new Promise((r) => setTimeout(r, 1000));
    }

    // Click "Plan Journey" button
    console.log('Clicking Plan Journey button...');
    const planBtn = await page.$('button[type="submit"]');
    if (planBtn) {
      await planBtn.click();
    }
    await new Promise((r) => setTimeout(r, 3500));

    // Screenshot 2: Journey Planned & Mode B Verified Live Tracking View
    console.log('Capturing Screenshot 2: Journey Planned & Verified Bus Tracking...');
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, '38_transit_app_redesign_journey_planned_and_tracking.png'),
      fullPage: false,
    });

    // Expand "View Technical & Telemetry Details" inside JourneyCard
    console.log('Expanding technical details...');
    await page.evaluate(() => {
      const details = Array.from(document.querySelectorAll('details'));
      details.forEach(d => {
        d.open = true;
      });
    });
    await new Promise((r) => setTimeout(r, 1000));

    // Screenshot 3: Expanded Telemetry on Demand
    console.log('Capturing Screenshot 3: Expanded Telemetry Details...');
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, '39_transit_app_redesign_expanded_telemetry.png'),
      fullPage: false,
    });

    console.log('All screenshots captured successfully!');
  } catch (err) {
    console.error('Error during capture:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

run();

