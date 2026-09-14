import { chromium, firefox, webkit } from '@playwright/test';

const family = process.argv[2];
const playerAddress = process.argv[3];
const studioAddress = process.argv[4];
const engine = { chromium, firefox, webkit }[family];
if (!engine || !playerAddress || !studioAddress) throw new Error('usage: node svg-scale-observe.mjs <family> <player-url> <studio-url>');
const external = family === 'chromium' ? process.env.PLAYWRIGHT_EXECUTABLE_PATH : family === 'firefox' ? process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH : process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH;
const browser = await engine.launch({ headless: true, executablePath: external || undefined });
try {
  const desktop = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const player = await desktop.newPage();
  await player.goto(playerAddress, { waitUntil: 'networkidle' });
  await player.waitForFunction(() => window.svgGeneratedScale);
  const snapshot = await player.evaluate(() => window.svgGeneratedScale.snapshot());
  if (snapshot.worldEntries !== 2000 || snapshot.visibleEntries !== 200 || snapshot.svgObjects !== 200 || snapshot.alternativeButtons !== 200 || snapshot.visitedChunks > 32) throw new Error(JSON.stringify(snapshot));
  const svgAlternative = await player.locator('#foundation-scale-host').ariaSnapshot();
  if (!svgAlternative.includes('Dense generated scale scene') || !svgAlternative.includes('Scale entity 200')) throw new Error('player accessibility alternative was incomplete');
  await desktop.close();

  const layouts = [];
  for (const layout of [
    { name: 'touch-390x844', width: 390, height: 844, touch: true, scale: 1 },
    { name: 'reflow-320', width: 320, height: 720, touch: false, scale: 1 },
    { name: 'zoom-400-percent-equivalent', width: 320, height: 720, touch: false, scale: 4 },
  ]) {
    const context = await browser.newContext({ viewport: { width: layout.width, height: layout.height }, hasTouch: layout.touch, deviceScaleFactor: layout.scale, reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.goto(playerAddress, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => window.svgGeneratedScale);
    const target = page.locator('[data-scale-entity="entity-99"]');
    await target.focus();
    if (!(await target.evaluate(element => element === document.activeElement))) throw new Error(`${layout.name}: alternative focus failed`);
    if (layout.touch) await page.locator('[data-scale-entity="entity-0"]').tap();
    const responsive = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches, focused: document.activeElement?.getAttribute('data-scale-entity'), svgWidth: document.querySelector('#foundation-scale-surface svg')?.getBoundingClientRect().width }));
    const expectedFocus = layout.touch ? 'entity-0' : 'entity-99';
    if (responsive.overflow > 1 || !responsive.reducedMotion || responsive.focused !== expectedFocus || responsive.svgWidth > layout.width) throw new Error(JSON.stringify({ layout, responsive }));
    layouts.push({ name: layout.name, ...responsive });
    await context.close();
  }

  const studioContext = await browser.newContext({ viewport: { width: 320, height: 720 }, reducedMotion: 'reduce' });
  const studio = await studioContext.newPage();
  await studio.goto(studioAddress, { waitUntil: 'networkidle' });
  await studio.waitForFunction(() => window.svgGeneratedStudio);
  const scene = studio.locator('#generated-authoring-studio--scene');
  await scene.focus();
  await studio.keyboard.press('Control+k');
  await studio.getByRole('dialog', { name: 'Command palette' }).waitFor();
  await studio.keyboard.press('Escape');
  const studioResult = await studio.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, focused: document.activeElement?.id, snapshot: window.svgGeneratedStudio.snapshot() }));
  if (studioResult.overflow > 1 || studioResult.focused !== 'generated-authoring-studio--scene') throw new Error(JSON.stringify(studioResult));
  await studioContext.close();
  process.stdout.write(JSON.stringify({ family, result: 'passed', player: snapshot, layouts, studio: { overflow: studioResult.overflow, focused: studioResult.focused }, reducedMotion: 'passed', keyboard: 'passed', touch: 'passed', alternatives: 'passed' }) + '\n');
} finally {
  await browser.close();
}
