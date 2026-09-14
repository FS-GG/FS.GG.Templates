import { chromium, firefox, webkit } from 'playwright';

const family = process.argv[2];
const baseURL = process.argv[3] ?? 'http://127.0.0.1:5100';
const engines = { chromium, firefox, webkit };
if (!engines[family]) throw new Error(`unknown browser family ${family}`);
const external = family === 'chromium' ? process.env.PLAYWRIGHT_EXECUTABLE_PATH : family === 'firefox' ? process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH : process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH;
const browser = await engines[family].launch({ headless: true, executablePath: external || undefined });
const diagnostics = [];
const contextA = await browser.newContext();
const contextB = await browser.newContext();
try {
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();
  for (const page of [pageA, pageB]) {
    page.on('pageerror', error => diagnostics.push({ kind: 'pageerror', detail: error.message }));
    page.on('requestfailed', request => diagnostics.push({ kind: 'requestfailed', detail: `${request.method()} ${request.url()}: ${request.failure()?.errorText}` }));
  }
  await Promise.all([pageA.goto(baseURL), pageB.goto(baseURL)]);
  await Promise.all([
    pageA.locator('#player-id').waitFor({ state: 'attached' }),
    pageB.locator('#player-id').waitFor({ state: 'attached' })
  ]);
  await pageA.waitForFunction(() => document.querySelector('#player-id')?.textContent);
  await pageB.waitForFunction(() => document.querySelector('#player-id')?.textContent);
  const playerA = await pageA.locator('#player-id').textContent();
  const playerB = await pageB.locator('#player-id').textContent();
  if (!playerA || !playerB || playerA === playerB) throw new Error('independent client identities were not assigned');
  await pageA.locator(`[data-occupant="${playerB}"]`).waitFor();
  await pageB.locator(`[data-occupant="${playerA}"]`).waitFor();

  const ownA = pageA.locator(`[data-occupant="${playerA}"]`);
  const [colA, rowA] = (await ownA.getAttribute('data-cell')).split('-').map(Number);
  const targetA = pageA.locator(`[data-cell="${colA}-${rowA + 1}"]`);
  await targetA.focus();
  if (!(await targetA.evaluate(element => element === document.activeElement))) throw new Error('client A target did not receive keyboard focus');
  await targetA.press('Enter');
  await pageB.locator(`[data-occupant="${playerA}"][data-cell="${colA}-${rowA + 1}"]`).waitFor();

  await targetA.focus();
  await pageA.evaluate(async () => await window.svgNetworkCandidate.sendRaw(JSON.stringify({
    kind: 'input', payload: { version: 1, sequence: 1, targetCol: 0, targetRow: 0 }
  })));
  await pageA.getByRole('status').waitFor();
  await pageA.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes('DuplicateInputSequence'));
  if (!(await targetA.evaluate(element => element === document.activeElement))) throw new Error('stale-input refusal displaced grid focus');

  await pageA.evaluate(async () => await window.svgNetworkCandidate.sendRaw(JSON.stringify({
    kind: 'input', payload: { version: 1, sequence: 2, targetCol: 999, targetRow: 999 }
  })));
  await pageA.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes('move.out-of-bounds'));

  const disconnect = pageA.getByRole('button', { name: 'Disconnect' });
  await disconnect.focus();
  await disconnect.press('Enter');
  await pageA.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes('closed'));
  const missedTick = Number((await pageA.locator('#tick').textContent()).replace(/\D/g, ''));

  const ownB = pageB.locator(`[data-occupant="${playerB}"]`);
  const [colB, rowB] = (await ownB.getAttribute('data-cell')).split('-').map(Number);
  const targetB = pageB.locator(`[data-cell="${colB}-${rowB + 1}"]`);
  await targetB.focus();
  if (!(await targetB.evaluate(element => element === document.activeElement))) throw new Error('client B target did not receive keyboard focus');
  await targetB.press('Enter');
  await pageB.locator(`[data-occupant="${playerB}"][data-cell="${colB}-${rowB + 1}"]`).waitFor();

  const reconnect = pageA.getByRole('button', { name: 'Reconnect and resync' });
  await reconnect.focus();
  await reconnect.press('Enter');
  await pageA.waitForFunction(() => document.querySelector('[role="status"]')?.textContent?.includes('synchronized'));
  await pageA.locator(`[data-occupant="${playerB}"][data-cell="${colB}-${rowB + 1}"]`).waitFor();
  const resyncedTick = Number((await pageA.locator('#tick').textContent()).replace(/\D/g, ''));
  if (resyncedTick <= missedTick) throw new Error(`resync did not advance beyond missed tick ${missedTick}`);
  if (!(await reconnect.evaluate(element => element === document.activeElement))) throw new Error('reconnect/resync displaced button focus');

  const [reviewA, reviewB] = await Promise.all([
    pageA.evaluate(async () => await (await fetch('/api/review')).json()),
    pageB.evaluate(async () => await (await fetch('/api/review')).json())
  ]);
  if (JSON.stringify(reviewA) !== JSON.stringify(reviewB)) throw new Error('clients observed different replay exports');
  if (reviewA.eventCount < 5 || !reviewA.accepted.includes(playerA) || !reviewA.accepted.includes(playerB)) throw new Error('accepted inputs were not recorded');
  const disclosure = JSON.stringify(reviewA);
  if (/sessionCapability|reconnectToken/i.test(disclosure)) throw new Error('review export disclosed a reconnect secret');

  if (diagnostics.length) throw new Error(JSON.stringify(diagnostics));
  process.stdout.write(JSON.stringify({ family, playerA, playerB, missedTick, resyncedTick, eventCount: reviewA.eventCount, replayBytes: reviewA.replay.length, disclosureSafe: true }) + '\n');
} finally {
  await contextA.close();
  await contextB.close();
  await browser.close();
}
