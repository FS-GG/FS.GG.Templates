import { chromium } from '@playwright/test';

const address = process.argv[2];
if (!address) throw new Error('usage: node svg-scale-measure.mjs <player-url>');
const browser = await chromium.launch({ headless: true });
const startupMs = [];
try {
  for (let index = 0; index < 5; index += 1) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const started = performance.now();
    await page.goto(address, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => window.svgGeneratedScale?.snapshot().svgObjects === 200);
    startupMs.push(performance.now() - started);
    await context.close();
  }
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto(address, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.svgGeneratedScale);
  const measured = await page.evaluate(async () => {
    const snapshotReadMs = [];
    for (let index = 0; index < 20; index += 1) {
      const started = performance.now();
      const snapshot = window.svgGeneratedScale.snapshot();
      snapshotReadMs.push(performance.now() - started);
      if (snapshot.worldEntries !== 2000 || snapshot.svgObjects !== 200) throw new Error(JSON.stringify(snapshot));
    }
    const animationFrameIntervalsMs = [];
    let previous = await new Promise(resolve => requestAnimationFrame(resolve));
    for (let index = 0; index < 120; index += 1) {
      const current = await new Promise(resolve => requestAnimationFrame(resolve));
      animationFrameIntervalsMs.push(current - previous);
      previous = current;
    }
    return { snapshotReadMs, animationFrameIntervalsMs, snapshot: window.svgGeneratedScale.snapshot() };
  });
  const percentile95 = values => [...values].sort((a, b) => a - b)[Math.ceil(values.length * 0.95) - 1];
  console.log(JSON.stringify({
    schema: 'fsgg.svg-preview-c.installed-scale-measurement/v1',
    browser: { family: 'chromium', version: browser.version(), headless: true },
    subject: { source: 'downloaded-public-template', worldEntries: measured.snapshot.worldEntries, visibleEntries: measured.snapshot.visibleEntries, svgObjects: measured.snapshot.svgObjects },
    startup: { samplesMs: startupMs, p95Ms: percentile95(startupMs) },
    snapshotRead: { samplesMs: measured.snapshotReadMs, p95Ms: percentile95(measured.snapshotReadMs) },
    animationFrame: { samples: measured.animationFrameIntervalsMs.length, intervalsMs: measured.animationFrameIntervalsMs, p95Ms: percentile95(measured.animationFrameIntervalsMs) },
    disposition: 'diagnostic-shared-runner; no new threshold or physical-device claim'
  }));
  await context.close();
} finally {
  await browser.close();
}
