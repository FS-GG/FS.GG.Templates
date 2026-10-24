#!/usr/bin/env node
import { polyglot_greet } from './domain.js';
const [command = 'hello', name = 'world'] = process.argv.slice(2);
if (command === 'hello') {
  process.stdout.write(polyglot_greet(name) + '\n');
} else {
  process.stderr.write(command === '--fail' ? 'requested failure\n' : 'usage: product-cli hello [name]\n');
  process.exitCode = 2;
}
