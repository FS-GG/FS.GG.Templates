import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { assessUpdates, parseArgs, resolveInside } from "./lib/xantham.mjs";

const root = resolve(import.meta.dirname, "..");
const args = parseArgs(process.argv.slice(2));
const baseline = JSON.parse(await readFile(resolve(root, "xantham/toolchain-lock.json"), "utf8"));
const assessment = await assessUpdates(baseline);
const schema = JSON.parse(await readFile(resolve(root, "xantham/schemas/update-assessment.schema.json"), "utf8"));
for (const field of schema.required) if (!(field in assessment)) throw new Error(`update assessment schema requires ${field}`);
if (!schema.properties.status.enum.includes(assessment.status)) throw new Error(`update assessment schema rejects status ${assessment.status}`);
if (!schema.properties.compatibility.enum.includes(assessment.compatibility)) throw new Error(`update assessment schema rejects compatibility ${assessment.compatibility}`);
const output = args.get("output");
if (output) {
  const path = resolveInside(root, output, "assessment output");
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(assessment, null, 2)}\n`);
}
console.log(JSON.stringify(assessment, null, 2));
if (assessment.status === "unavailable") process.exitCode = 2;
