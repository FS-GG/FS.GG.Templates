import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { hashFile, parseArgs, resolveInside } from "./lib/xantham.mjs";

const root = resolve(import.meta.dirname, "..");
const repositoryRoot = resolve(root, "../..");
const args = parseArgs(process.argv.slice(2));
const toolDir = resolveInside(root, args.get("tool-dir") ?? ".nuget/xantham-tools", "tool directory");
const lock = JSON.parse(await readFile(resolve(root, "xantham/toolchain-lock.json"), "utf8"));
if (process.platform !== "linux" || process.arch !== "x64") throw new Error(`Xantham preparation is qualified only for linux-x64; found ${process.platform}-${process.arch}`);

const run = (command, argv, cwd, env) => new Promise((accept, reject) => {
  const child = spawn(command, argv, { cwd, env, stdio: "inherit" });
  child.once("error", reject);
  child.once("exit", code => code === 0 ? accept() : reject(new Error(`${command} exited ${code}`)));
});

await mkdir(resolve(toolDir, "bin"), { recursive: true });
await mkdir(resolve(toolDir, "compiler"), { recursive: true });
await mkdir(resolve(toolDir, "pilot"), { recursive: true });
await mkdir(resolve(toolDir, "home"), { recursive: true });
await mkdir(resolve(toolDir, "npm-cache"), { recursive: true });
await writeFile(resolve(toolDir, "home/.npmrc"), "ignore-scripts=true\n");
await cp(resolve(root, "xantham/compiler/package.json"), resolve(toolDir, "compiler/package.json"));
await cp(resolve(root, "xantham/compiler/package-lock.json"), resolve(toolDir, "compiler/package-lock.json"));
await cp(resolve(root, "xantham/pilot/package.json"), resolve(toolDir, "pilot/package.json"));
await cp(resolve(root, "xantham/pilot/package-lock.json"), resolve(toolDir, "pilot/package-lock.json"));

const isolatedEnv = {
  ...process.env,
  HOME: resolve(toolDir, "home"),
  DOTNET_CLI_HOME: resolve(toolDir, "home/dotnet"),
  NPM_CONFIG_CACHE: resolve(toolDir, "npm-cache"),
  NPM_CONFIG_USERCONFIG: resolve(toolDir, "home/.npmrc"),
  DOTNET_NOLOGO: "1",
  DOTNET_SKIP_FIRST_TIME_EXPERIENCE: "1"
};
for (const key of Object.keys(isolatedEnv)) if (key.toLowerCase() === "npm_config_allow_scripts") delete isolatedEnv[key];
await run("dotnet", ["tool", "install", lock.cli.package, "--version", lock.cli.version, "--tool-path", resolve(toolDir, "bin")], repositoryRoot, isolatedEnv).catch(async error => {
  const existing = await hashFile(resolve(toolDir, "bin/xantham")).catch(() => null);
  if (existing !== lock.cli.linuxX64ApphostSha256) throw error;
});
await run("npm", ["ci", "--ignore-scripts"], resolve(toolDir, "compiler"), isolatedEnv);
await run("npm", ["ci", "--ignore-scripts"], resolve(toolDir, "pilot"), isolatedEnv);

const cli = resolve(toolDir, "bin/xantham");
const compiler = resolve(toolDir, "compiler", lock.compiler.linuxX64Executable);
const packageRoot = resolve(toolDir, "bin/.store/xantham", lock.cli.version, "xantham", lock.cli.version);
const generatorAssembly = resolve(packageRoot, "tools/net10.0/any/Xantham.Generator.dll");
const packageHash = (await readFile(resolve(packageRoot, `xantham.${lock.cli.version}.nupkg.sha512`), "utf8")).trim();
const observed = { cliApphostSha256: await hashFile(cli), cliPackageSha512: packageHash, generatorAssemblySha256: await hashFile(generatorAssembly), compilerSha256: await hashFile(compiler) };
if (observed.cliApphostSha256 !== lock.cli.linuxX64ApphostSha256) throw new Error(`prepared Xantham apphost hash mismatch: expected ${lock.cli.linuxX64ApphostSha256}, found ${observed.cliApphostSha256}`);
if (observed.cliPackageSha512 !== lock.cli.packageSha512) throw new Error(`prepared Xantham package hash mismatch: expected ${lock.cli.packageSha512}, found ${observed.cliPackageSha512}`);
if (observed.generatorAssemblySha256 !== lock.cli.generatorAssemblySha256) throw new Error(`prepared Xantham generator assembly hash mismatch: expected ${lock.cli.generatorAssemblySha256}, found ${observed.generatorAssemblySha256}`);
if (observed.compilerSha256 !== lock.compiler.linuxX64Sha256) throw new Error(`prepared compiler hash mismatch: expected ${lock.compiler.linuxX64Sha256}, found ${observed.compilerSha256}`);
await writeFile(resolve(toolDir, "prepared.json"), `${JSON.stringify({ schemaVersion: 1, ...observed, cli, compiler }, null, 2)}\n`);
console.log(`prepared exact Xantham ${lock.cli.version} and TypeScript ${lock.compiler.version} under ${toolDir}`);
