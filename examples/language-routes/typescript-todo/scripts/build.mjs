import { cp, mkdir, rm } from "node:fs/promises";
import { spawn } from "node:child_process";

const root = new URL("../", import.meta.url);
const dist = new URL("dist/", root);
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

const compiler = new URL("node_modules/typescript/bin/tsc", root);
await new Promise((resolve, reject) => {
  const child = spawn(process.execPath, [compiler.pathname, "--project", new URL("tsconfig.json", root).pathname], { cwd: root, stdio: "inherit" });
  child.on("error", reject);
  child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`TypeScript compiler exited ${code}`)));
});
await cp(new URL("public/", root), dist, { recursive: true });
console.log("compiled TypeScript todo and staged its browser entry point");
