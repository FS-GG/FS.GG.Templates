import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';

export const root = resolve(import.meta.dirname, '..');
export const apps = ['todo', 'tic-tac-toe', 'snake', 'hello-world'];
export const output = resolve(root, '.artifacts/site');
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
const files = [];
for (const app of apps) {
  const entries = await readdir(resolve(root, app), { withFileTypes: true });
  if (!entries.some(entry => entry.name === 'index.html' && entry.isFile())) throw new Error(`${app}: missing application entry`);
  await mkdir(resolve(output, app));
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isFile() || !/\.(?:html|css|js|mjs)$/.test(entry.name) || /\.(?:test|spec)\.mjs$/.test(entry.name)) continue;
    const bytes = await readFile(resolve(root, app, entry.name));
    await writeFile(resolve(output, app, entry.name), bytes);
    files.push({ path: `${app}/${entry.name}`, sha256: createHash('sha256').update(bytes).digest('hex') });
  }
}
await writeFile(resolve(output, 'index.html'), `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Enrolled browser apps</title><main><h1>Enrolled browser apps</h1><ul>${apps.map(app => `<li><a href="./${app}/">${app}</a></li>`).join('')}</ul></main></html>\n`);
await writeFile(resolve(root, '.artifacts/source-manifest.json'), JSON.stringify({ schema: 'fs-gg.enrollment-app-source/1', files }, null, 2) + '\n');
console.log(`Staged ${files.length} exact source assets for ${apps.length} apps.`);
