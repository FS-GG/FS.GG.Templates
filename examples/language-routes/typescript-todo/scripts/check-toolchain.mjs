import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import process from "node:process";

const root = new URL("../", import.meta.url);
const lock = JSON.parse(await readFile(new URL("toolchain-lock.json", root), "utf8"));
const packageLock = JSON.parse(await readFile(new URL("package-lock.json", root), "utf8"));
const moduleRoot = process.env.TYPESCRIPT_TODO_MODULE_ROOT
  ? resolve(process.env.TYPESCRIPT_TODO_MODULE_ROOT)
  : new URL("node_modules/", root).pathname;
const installedCompiler = JSON.parse(await readFile(resolve(moduleRoot, "typescript/package.json"), "utf8"));
const installedPlaywright = JSON.parse(await readFile(resolve(moduleRoot, "@playwright/test/package.json"), "utf8"));

function requireExact(actual, expected, name) {
  if (actual !== expected) throw new Error(`${name} must be exactly ${expected}; found ${actual}`);
}

requireExact(packageLock.packages["node_modules/typescript"].version, lock.typescript, "locked TypeScript");
requireExact(installedCompiler.version, lock.typescript, "installed TypeScript");
requireExact(packageLock.packages["node_modules/@playwright/test"].version, lock.playwright, "locked Playwright");
requireExact(installedPlaywright.version, lock.playwright, "installed Playwright");

const actualNode = process.versions.node;
const selected = actualNode === lock.node;
console.log(JSON.stringify({
  schema: "fsgg.v2-lang.typescript-toolchain-check/1",
  typescript: installedCompiler.version,
  selectedNode: lock.node,
  actualNode,
  disposition: selected ? "qualification-candidate" : "preparatory-host-version-mismatch",
  qualificationImage: lock.qualificationImage,
}));
