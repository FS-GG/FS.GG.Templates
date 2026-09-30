import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import process from "node:process";

const root = new URL("../", import.meta.url);
const lock = JSON.parse(await readFile(new URL("toolchain-lock.json", root), "utf8"));
if (process.versions.node !== lock.node) {
  throw new Error(`selected qualification requires Node ${lock.node}; found ${process.versions.node}`);
}
const archive = process.env.TYPESCRIPT_TODO_NODE_ARCHIVE;
if (!archive) throw new Error("TYPESCRIPT_TODO_NODE_ARCHIVE must identify the reviewed official Node archive");
const hash = createHash("sha256");
await new Promise((resolve, reject) => createReadStream(archive).on("data", (chunk) => hash.update(chunk)).on("end", resolve).on("error", reject));
if (hash.digest("hex") !== lock.nodeArchive.sha256) throw new Error("Node archive SHA-256 does not match the reviewed pin");
const output = process.env.TYPESCRIPT_TODO_OUTPUT
  ? resolve(process.env.TYPESCRIPT_TODO_OUTPUT)
  : await mkdtemp(join(tmpdir(), "fsgg-typescript-todo-"));
await mkdir(join(output, "dist"), { recursive: true });
await mkdir(join(output, "reports"), { recursive: true });
await mkdir(join(output, "cache"), { recursive: true });
await mkdir(join(output, "home"), { recursive: true });
await mkdir(join(output, "tmp"), { recursive: true });
const scopedEnvironment = {
  HOME: join(output, "home"),
  XDG_CACHE_HOME: join(output, "cache"),
  TMPDIR: join(output, "tmp"),
  TYPESCRIPT_TODO_DIST_DIR: join(output, "dist"),
  TYPESCRIPT_TODO_REPORT_DIR: join(output, "reports"),
  TYPESCRIPT_TODO_NODE: process.execPath,
  TYPESCRIPT_TODO_SERVE_SCRIPT: new URL("scripts/serve.mjs", root).pathname,
};

async function run(args, extraEnvironment = {}) {
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, {
      cwd: root,
      stdio: "inherit",
      env: { ...process.env, ...scopedEnvironment, ...extraEnvironment },
    });
    child.on("error", reject);
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`${args[0]} exited ${code}`)));
  });
}

await run([new URL("scripts/check-toolchain.mjs", root).pathname]);
await run([new URL("scripts/build.mjs", root).pathname]);
await run(["--test", "tests/domain.test.mjs", "tests/storage.test.mjs", "tests/toolchain.test.mjs"]);
await run([new URL("node_modules/@playwright/test/cli.js", root).pathname, "test"], { TYPESCRIPT_TODO_NODE: process.execPath });
console.log(JSON.stringify({
  schema: "fsgg.v2-lang.typescript-todo-native-qualification/1",
  node: process.versions.node,
  nodeArchiveSha256: lock.nodeArchive.sha256,
  typescript: lock.typescript,
  compiler: "exact",
  unitTests: "passed",
  servedBrowserJourney: "passed",
  qualificationImage: lock.qualificationImage,
  output,
  scope: "native-fixture-only",
}));
