import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, extname, normalize, relative, resolve } from "node:path";
import { loadCorpus, lockIdentity } from "./corpus.mjs";

const args = process.argv.slice(2);
const valueAfter = flag => {
  const index = args.indexOf(flag);
  return index < 0 ? undefined : args[index + 1];
};
const root = resolve(valueAfter("--declarations-root") ?? resolve(import.meta.dirname, "..", "node_modules"));
const lockPath = resolve(valueAfter("--lock") ?? resolve(import.meta.dirname, "..", "declaration-lock.json"));
const corpus = await loadCorpus(resolve(valueAfter("--corpus") ?? resolve(import.meta.dirname, "..", "corpus.json")));
const entryPoints = valueAfter("--entry") ? [valueAfter("--entry")] : corpus.declarationEntryPoints;
// The closure is labelled with the corpus pins, so the installed artifacts must be exactly those.
if (!valueAfter("--entry")) {
  for (const { name, version } of corpus.npmArtifacts) {
    const installed = JSON.parse(await readFile(resolve(root, name, "package.json"), "utf8")).version;
    if (installed !== version) throw new Error(`installed ${name}@${installed} differs from corpus pin ${version}; run npm ci or review the corpus`);
  }
}

const declarationPath = (from, specifier) => {
  const requested = normalize(resolve(dirname(resolve(root, from)), specifier));
  if (!requested.startsWith(`${root}/`)) throw new Error(`relative declaration escaped root: ${from} -> ${specifier}`);
  const extension = extname(requested);
  const declaration = extension === ".js" ? `${requested.slice(0, -3)}.d.ts` : extension ? requested : `${requested}.d.ts`;
  return relative(root, declaration).replaceAll("\\", "/");
};

// Covers re-exports, dynamic imports, and static side-effect imports.
const references = source => [...source.matchAll(/(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)["'](\.{1,2}\/[^"]+?)["']/g)].map(match => match[1]);
const seen = new Set();
const pending = [...entryPoints].sort();
while (pending.length > 0) {
  const path = pending.shift();
  if (seen.has(path)) continue;
  const source = await readFile(resolve(root, path), "utf8");
  seen.add(path);
  for (const specifier of references(source)) pending.push(declarationPath(path, specifier));
  pending.sort();
}

const files = await Promise.all([...seen].sort().map(async path => ({
  path,
  sha256: createHash("sha256").update(await readFile(resolve(root, path))).digest("hex")
})));
const document = { schema: 2, ...lockIdentity(corpus), entryPoints, files };
const rendered = `${JSON.stringify(document, null, 2)}\n`;
if (args.includes("--write")) {
  await writeFile(lockPath, rendered);
  console.log(`wrote ${lockPath} (${files.length} declaration files)`);
} else {
  if (await readFile(lockPath, "utf8") !== rendered) throw new Error("declaration closure drifted; review the lock, curated bindings, runtime evidence, and release notes together");
  console.log(`declaration closure is locked (${files.length} declaration files)`);
}
