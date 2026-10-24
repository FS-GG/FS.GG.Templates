import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { polyglot_greet } from '../src/domain.js';
const entry = fileURLToPath(new URL('../src/main.js', import.meta.url));
test('domain preserves literal text', () => assert.equal(polyglot_greet('$(literal);& with spaces'), 'hello $(literal);& with spaces'));
test('actual CLI preserves argv and exits honestly', () => {
 const ok = spawnSync(process.execPath, [entry, 'hello', '$(literal);& with spaces'], { encoding: 'utf8' });
 assert.equal(ok.status, 0); assert.equal(ok.stdout, 'hello $(literal);& with spaces\n');
 const bad = spawnSync(process.execPath, [entry, '--fail'], { encoding: 'utf8' });
 assert.equal(bad.status, 2); assert.equal(bad.stderr, 'requested failure\n');
});
