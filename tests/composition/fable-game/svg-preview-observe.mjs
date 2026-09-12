import { chromium } from '@playwright/test';

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined;
const address = process.argv[2];
if (!address) throw new Error('usage: node svg-preview-observe.mjs <address>');

const browser = await chromium.launch({ headless: true, executablePath });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(address, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-scene-root-id="foundation-grid"]');
await page.waitForSelector('[data-fsgg-document-id="preview-a-generated-consumer"]');
await page.evaluate(() => document.fonts.ready);

const exported = await page.locator('#foundation-preview-export').textContent();
const observed = await page.evaluate(() => {
  const hasLocalRef = (root, value) => {
    const match = value?.match(/^url\(#(.+)\)$/) ?? value?.match(/^#(.+)$/);
    return !!match && !!root.querySelector(`[id="${CSS.escape(match[1])}"]`);
  };
  const documentRoot = document.querySelector('[data-fsgg-document-id="preview-a-generated-consumer"]');
  const route = documentRoot?.querySelector('[data-fsgg-semantic-id="semantic:fractional-route"]');
  const routeShape = route?.querySelector('path');
  const bounds = routeShape?.getBoundingClientRect();
  return {
    title: document.title,
    roots: [...document.querySelectorAll('[data-scene-root-id]')].map(x => x.getAttribute('data-scene-root-id')),
    selected: document.querySelector('[data-scene-root-id="tactical-compatibility"] [data-selected="true"]')?.getAttribute('data-scene-object-id'),
    focusable: document.querySelector('[data-scene-root-id="tactical-compatibility"] [data-focused="true"]')?.getAttribute('data-scene-object-id'),
    document: documentRoot?.getAttribute('data-fsgg-document-id'),
    documentSelection: documentRoot?.getAttribute('data-preview-selected-semantic'),
    gradients: documentRoot?.querySelectorAll('linearGradient').length,
    clips: documentRoot?.querySelectorAll('clipPath').length,
    masks: documentRoot?.querySelectorAll('mask').length,
    symbols: documentRoot?.querySelectorAll('symbol').length,
    uses: documentRoot?.querySelectorAll('use').length,
    texts: documentRoot?.querySelectorAll('text').length,
    transformed: route?.getAttribute('transform')?.startsWith('matrix('),
    clipped: [...(route?.querySelectorAll('[clip-path]') ?? [])].length === 2 && [...route.querySelectorAll('[clip-path]')].every(x => hasLocalRef(documentRoot, x.getAttribute('clip-path'))),
    masked: hasLocalRef(documentRoot, route?.getAttribute('mask')),
    gradientPaint: hasLocalRef(documentRoot, routeShape?.getAttribute('fill')) && getComputedStyle(routeShape).fill.startsWith('url('),
    fontReady: document.fonts.check('12px "Noto Sans Preview"'),
    routeBounds: bounds ? { width: bounds.width, height: bounds.height } : null
  };
});

if (!observed.roots.includes('foundation-continuous') || !observed.roots.includes('tactical-compatibility') || observed.selected !== 'unit:7' || observed.focusable !== 'unit:11') throw new Error(JSON.stringify(observed));
if (observed.document !== 'preview-a-generated-consumer' || observed.documentSelection !== 'semantic:fractional-route' || observed.gradients !== 1 || observed.clips !== 2 || observed.masks !== 2 || observed.symbols !== 1 || observed.uses !== 1 || observed.texts < 1 || !observed.transformed || !observed.clipped || !observed.masked || !observed.gradientPaint || !observed.fontReady || !observed.routeBounds || observed.routeBounds.width <= 0 || observed.routeBounds.height <= 0) throw new Error(JSON.stringify(observed));
if (!exported.includes('<linearGradient') || !exported.includes('clip-path="url(#') || !exported.includes('mask="url(#')) throw new Error('exported definitions or local references drifted');

const isolated = await page.evaluate(async (svg) => {
  const frame = document.createElement('iframe');
  frame.setAttribute('title', 'isolated exported Preview-A SVG');
  const loaded = new Promise((resolve, reject) => {
    frame.onload = resolve;
    setTimeout(() => reject(new Error('isolated export timeout')), 5000);
  });
  frame.srcdoc = svg;
  document.body.appendChild(frame);
  await loaded;
  const root = frame.contentDocument?.querySelector('svg[data-fsgg-document-id]');
  await frame.contentDocument?.fonts.ready;
  const hasLocalRef = (value) => {
    const match = value?.match(/^url\(#(.+)\)$/) ?? value?.match(/^#(.+)$/);
    return !!match && !!root?.querySelector(`[id="${CSS.escape(match[1])}"]`);
  };
  const route = root?.querySelector('[data-fsgg-semantic-id="semantic:fractional-route"]');
  const routeShape = route?.querySelector('path');
  const bounds = routeShape?.getBoundingClientRect();
  const value = {
    document: root?.getAttribute('data-fsgg-document-id'),
    gradient: root?.querySelectorAll('linearGradient').length,
    uses: root?.querySelectorAll('use').length,
    gradientPaint: hasLocalRef(routeShape?.getAttribute('fill')) && frame.contentWindow?.getComputedStyle(routeShape).fill.startsWith('url('),
    localReferences: [...(root?.querySelectorAll('*') ?? [])].every(node =>
      ['fill', 'stroke', 'clip-path', 'mask', 'href'].every(name => {
        const value = node.getAttribute(name);
        return !value?.startsWith('url(#') && !value?.startsWith('#') || hasLocalRef(value);
      })),
    fontReady: frame.contentDocument?.fonts.check('12px "Noto Sans Preview"'),
    width: bounds?.width ?? 0,
    height: bounds?.height ?? 0
  };
  frame.remove();
  return value;
}, exported);

if (isolated.document !== 'preview-a-generated-consumer' || isolated.gradient !== 1 || isolated.uses !== 1 || !isolated.gradientPaint || !isolated.localReferences || !isolated.fontReady || isolated.width <= 0 || isolated.height <= 0) throw new Error(JSON.stringify(isolated));
observed.isolatedExport = isolated;
console.log(JSON.stringify(observed));
await browser.close();
