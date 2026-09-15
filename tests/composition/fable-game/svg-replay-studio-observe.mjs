import { chromium, firefox, webkit } from '@playwright/test';

const [family, url] = process.argv.slice(2);
const engines = { chromium, firefox, webkit };
if (!engines[family] || !url) throw new Error('usage: node svg-replay-studio-observe.mjs <chromium|firefox|webkit> <url>');
const external = family === 'chromium' ? process.env.PLAYWRIGHT_EXECUTABLE_PATH : family === 'firefox' ? process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH : process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH;
const browser = await engines[family].launch({ headless: true, executablePath: external || undefined });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', error => errors.push(String(error)));
await page.goto(url, { waitUntil: 'networkidle' });

const press = async label => {
  const button = page.getByRole('button', { name: label, exact: true });
  await button.focus();
  await page.keyboard.press('Enter');
};
await press('Open starter game');
const beforePlay = await page.evaluate(() => window.svgGeneratedStudio.snapshot());
await press('Play edited arena step');
await press('Move edited player right');
const accepted = await page.evaluate(() => window.svgGeneratedStudio.snapshot());
if (accepted.playCanonicalState === beforePlay.playCanonicalState || accepted.replay.recordedEvents < 3)
  throw new Error(JSON.stringify({ beforePlay, accepted }));

await press('Replay complete arena recording');
const replay = await page.locator('#generated-replay-timeline output').textContent();
await press('Seek arena replay checkpoint');
const seek = await page.locator('#generated-replay-timeline output').textContent();
await press('Cancel arena replay safely');
const cancel = await page.locator('#generated-replay-timeline output').textContent();
await press('Diagnose arena replay divergence');
const divergence = await page.locator('#generated-replay-inspector output').textContent();
await press('Branch and compare arena scenario');
const planning = await page.locator('#generated-scenario-planner output').textContent();
await press('Explain arena goal rule');
const rule = await page.locator('#generated-rule-explorer output').textContent();
const snapshot = await page.evaluate(() => window.svgGeneratedStudio.snapshot());
const panels = await page.locator('section[tabindex="0"][aria-label]').count();
const result = { family, errors, replay, seek, cancel, divergence, planning, rule, panels, accepted, snapshot };
if (errors.length || panels !== 4) throw new Error(JSON.stringify(result));
if (!replay.includes(`Replayed ${accepted.replay.recordedEvents} arena events`) || snapshot.replay.acceptedDigest !== accepted.playCanonicalState) throw new Error(JSON.stringify(result));
if (!seek.includes('Seeked to') || !seek.includes('collected') || !cancel.includes('Cancelled before event 2')) throw new Error(JSON.stringify(result));
if (!divergence.includes('First divergence at event 2') || !divergence.includes('expected mutated') || !divergence.includes('actual v3|')) throw new Error(JSON.stringify(result));
if (!planning.includes('Accepted and predicted arena states compared') || !planning.includes('scenario cancelled through Planning.cancel')) throw new Error(JSON.stringify(result));
if (!rule.includes('arena.collect then arena.goal') || !rule.includes('disclosed causes') || rule.includes('hidden') || rule.includes('server-only')) throw new Error(JSON.stringify(result));
if (!snapshot.replay.disclosureSafe || snapshot.replay.authoredContentId !== snapshot.gameplayContentId || snapshot.replay.predictedDigest !== snapshot.replay.acceptedDigest) throw new Error(JSON.stringify(result));
console.log(JSON.stringify(result));
await browser.close();
