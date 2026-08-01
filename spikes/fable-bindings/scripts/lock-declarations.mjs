import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const lockPath = resolve(root, "declaration-lock.json");
const entries = [
  "@babylonjs/core/Engines/nullEngine.d.ts",
  "@babylonjs/core/scene.d.ts",
  "@babylonjs/core/Maths/math.vector.d.ts",
  "@babylonjs/core/Cameras/freeCamera.d.ts",
  "@babylonjs/core/Lights/hemisphericLight.d.ts",
  "@babylonjs/core/Meshes/meshBuilder.d.ts",
  "@babylonjs/loaders/glTF/index.d.ts"
];
const files = await Promise.all(entries.map(async path => ({
  path,
  sha256: createHash("sha256").update(await readFile(resolve(root, "node_modules", path))).digest("hex")
})));
const document = { schema: 1, package: "@babylonjs/core@9.19.0", companionPackage: "@babylonjs/loaders@9.19.0", entryPoints: entries, files };
const rendered = `${JSON.stringify(document, null, 2)}\n`;
if (process.argv.includes("--write")) {
  await writeFile(lockPath, rendered);
  console.log(`wrote ${lockPath}`);
} else {
  if (await readFile(lockPath, "utf8") !== rendered) throw new Error("declaration closure drifted; review the lock, curated bindings, runtime evidence, and release notes together");
  console.log("declaration closure is locked");
}
