import { cp, mkdir, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const root = new URL("../", import.meta.url);
const dist = process.env.TYPESCRIPT_TODO_DIST_DIR
  ? pathToFileURL(`${resolve(process.env.TYPESCRIPT_TODO_DIST_DIR)}/`)
  : new URL("dist/", root);
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

const compiler = process.env.TYPESCRIPT_TODO_TYPESCRIPT_BIN
  ? resolve(process.env.TYPESCRIPT_TODO_TYPESCRIPT_BIN)
  : new URL("node_modules/typescript/bin/tsc", root).pathname;
await new Promise((resolve, reject) => {
  const child = spawn(process.execPath, [compiler, "--project", new URL("tsconfig.json", root).pathname, "--outDir", dist.pathname], { cwd: root, stdio: "inherit" });
  child.on("error", reject);
  child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`TypeScript compiler exited ${code}`)));
});
await cp(new URL("public/", root), dist, { recursive: true });
console.log("compiled TypeScript todo and staged its browser entry point");
