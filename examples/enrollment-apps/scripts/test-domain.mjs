import { readdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const tests = [];
for (const app of ['todo', 'tic-tac-toe', 'snake']) {
  const names = (await readdir(resolve(root, app))).filter(name => name.endsWith('.test.mjs')).sort();
  if (!names.length) throw new Error(`${app}: missing meaningful domain tests`);
  tests.push(...names.map(name => `${app}/${name}`));
}
const result = spawnSync(process.execPath, ['--test', ...tests], { cwd: root, stdio: 'inherit' });
process.exit(result.status ?? 1);
