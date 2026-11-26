import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  for (const job of jobs) {
    await page.goto(pathToFileURL(job.page).href);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: job.png });
  }
} finally {
  await browser.close();
}
