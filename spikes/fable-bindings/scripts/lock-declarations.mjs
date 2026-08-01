import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, extname, normalize, relative, resolve } from "node:path";

const args = process.argv.slice(2);
const valueAfter = flag => {
  const index = args.indexOf(flag);
  return index < 0 ? undefined : args[index + 1];
};
const root = resolve(valueAfter("--declarations-root") ?? resolve(import.meta.dirname, "..", "node_modules"));
const lockPath = resolve(valueAfter("--lock") ?? resolve(import.meta.dirname, "..", "declaration-lock.json"));
const entryPoints = valueAfter("--entry") ? [valueAfter("--entry")] : [
  "@babylonjs/core/Engines/nullEngine.d.ts",
  "@babylonjs/core/scene.d.ts",
  "@babylonjs/core/Maths/math.vector.d.ts",
  "@babylonjs/core/Cameras/freeCamera.d.ts",
  "@babylonjs/core/Lights/hemisphericLight.d.ts",
  "@babylonjs/core/Meshes/meshBuilder.d.ts",
  "@babylonjs/loaders/glTF/index.d.ts"
];

const declarationPath = (from, specifier) => {
  const requested = normalize(resolve(dirname(resolve(root, from)), specifier));
  if (!requested.startsWith(`${root}/`)) throw new Error(`relative declaration escaped root: ${from} -> ${specifier}`);
  const extension = extname(requested);
  const declaration = extension === ".js" ? `${requested.slice(0, -3)}.d.ts` : extension ? requested : `${requested}.d.ts`;
  return relative(root, declaration).replaceAll("\\", "/");
};

const references = source => [...source.matchAll(/(?:\bfrom\s*|\bimport\s*\()["'](\.{1,2}\/[^"]+?)["']/g)].map(match => match[1]);
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
const document = { schema: 2, package: "@babylonjs/core@9.19.0", companionPackage: "@babylonjs/loaders@9.19.0", entryPoints, files };
const rendered = `${JSON.stringify(document, null, 2)}\n`;
if (args.includes("--write")) {
  await writeFile(lockPath, rendered);
  console.log(`wrote ${lockPath} (${files.length} declaration files)`);
} else {
  if (await readFile(lockPath, "utf8") !== rendered) throw new Error("declaration closure drifted; review the lock, curated bindings, runtime evidence, and release notes together");
  console.log(`declaration closure is locked (${files.length} declaration files)`);
}
