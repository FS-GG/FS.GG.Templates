import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { cp, lstat, mkdir, readFile, readdir, realpath, rename, stat, writeFile } from "node:fs/promises";
import { relative, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile, parseArgs, rejectSymlinkPath, resolveInside, sha256, validateXanthamCandidate } from "./lib/xantham.mjs";

const root = resolve(import.meta.dirname, "..");
const repositoryRoot = resolve(root, "../..");
const generatedRoot = resolve(root, "generated-candidates");
const candidatesRoot = resolve(generatedRoot, "xantham");
const args = parseArgs(process.argv.slice(2));
const configArgument = args.get("config") ?? "";
const toolDirectoryArgument = args.get("tool-dir") ?? ".nuget/xantham-tools";
const runId = `${new Date().toISOString().replace(/[:.]/g, "-")}-${randomUUID().slice(0, 8)}`;

const generatedInfo = await lstat(generatedRoot);
if (generatedInfo.isSymbolicLink() || !generatedInfo.isDirectory()) throw new Error("generated-candidates must be a real directory");
const generatedCanonical = await realpath(generatedRoot);
if (relative(root, generatedCanonical).startsWith(`..${sep}`)) throw new Error("generated-candidates resolves outside the workspace");
const xanthamInfo = await lstat(candidatesRoot).catch(error => error.code === "ENOENT" ? null : Promise.reject(error));
if (xanthamInfo?.isSymbolicLink() || (xanthamInfo && !xanthamInfo.isDirectory())) throw new Error("generated-candidates/xantham must be a real directory");
await mkdir(candidatesRoot, { recursive: true });
const runsRoot = resolve(candidatesRoot, "runs");
const runsInfo = await lstat(runsRoot).catch(error => error.code === "ENOENT" ? null : Promise.reject(error));
if (runsInfo?.isSymbolicLink() || (runsInfo && !runsInfo.isDirectory())) throw new Error("generated-candidates/xantham/runs must be a real directory");
const runDir = resolve(runsRoot, runId);
const rawDir = resolve(runDir, "raw");
const scratchDir = resolve(root, ".nuget/xantham-scratch", runId);
const homeDir = resolve(scratchDir, "home");
await mkdir(rawDir, { recursive: true }); await mkdir(homeDir, { recursive: true });
const reportPath = resolve(runDir, "run-report.json");

const started = new Date(); const diagnostics = []; const phaseDurationsMs = {};
let configBytes = Buffer.alloc(0); let toolchainBytes = Buffer.alloc(0); let config = null; let toolchain = null; let manifest = null; let toolDir = null;
let cliVersion = null; let compilerVersion = null; let artifactHashes = {}; let beforeMaintained = null; let afterMaintained = null; let status = "rejected";
const processRecord = { command: [], exitCode: null, signal: null, limits: null, stdout: "stdout.log", stderr: "stderr.log", limitTriggered: null };
const verification = { reportSchema: "not-run", limits: "not-run", imports: "not-run", selectedSymbols: "not-run", fsharpCompile: "not-run", fableCompile: "not-run", runtime: "not-run" };

const walkFiles = async dir => {
  const result = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`generated output contains symlink: ${path}`);
    if (entry.isDirectory()) result.push(...await walkFiles(path)); else result.push(path);
  }
  return result.sort();
};
const directorySize = async dir => { let total = 0; for (const path of await walkFiles(dir).catch(() => [])) total += (await stat(path)).size; return total; };
const maintained = ["src", "declaration-lock.json", "binding-plan.json", "coverage-and-drift.json"];
const hashMaintained = async () => {
  const digest = createHash("sha256");
  for (const item of maintained) {
    const path = resolve(root, item); const files = (await stat(path)).isDirectory() ? await walkFiles(path) : [path];
    for (const file of files) digest.update(relative(root, file)).update(await readFile(file));
  }
  return digest.digest("hex");
};
const groupRss = async groupId => {
  let total = 0;
  for (const entry of await readdir("/proc", { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^\d+$/.test(entry.name)) continue;
    try {
      const text = await readFile(`/proc/${entry.name}/stat`, "utf8");
      const fields = text.slice(text.lastIndexOf(")") + 2).split(" ");
      if (Number(fields[2]) !== groupId) continue;
      total += Number((await readFile(`/proc/${entry.name}/statm`, "utf8")).split(" ")[1]) * 4096;
    } catch {}
  }
  return total;
};
const boundedProcess = (command, argv, { cwd, env, timeoutMs, logBytes, rssBytes = null, outputDir = null, outputBytes = null }) => new Promise((accept, reject) => {
  const child = spawn(command, argv, { cwd, env, detached: true, stdio: ["ignore", "pipe", "pipe"] });
  let stdout = Buffer.alloc(0); let stderr = Buffer.alloc(0); let trigger = null; let stopped = false;
  const stop = reason => { if (!stopped) { stopped = true; trigger = reason; try { process.kill(-child.pid, "SIGKILL"); } catch {} } };
  child.stdout.on("data", bytes => { stdout = Buffer.concat([stdout, bytes]); if (stdout.length > logBytes) stop("stdout-bytes"); });
  child.stderr.on("data", bytes => { stderr = Buffer.concat([stderr, bytes]); if (stderr.length > logBytes) stop("stderr-bytes"); });
  const timer = setTimeout(() => stop("timeout"), timeoutMs);
  const watcher = setInterval(async () => {
    try {
      if (outputDir && await directorySize(outputDir) > outputBytes) stop("output-bytes");
      else if (rssBytes && await groupRss(child.pid) > rssBytes) stop("sampled-process-group-rss");
    } catch (error) { stop(`monitor-error:${error.message}`); }
  }, 100);
  child.once("error", error => { clearTimeout(timer); clearInterval(watcher); reject(error); });
  child.once("exit", (code, signal) => { clearTimeout(timer); clearInterval(watcher); accept({ code, signal, stdout: stdout.subarray(0, logBytes), stderr: stderr.subarray(0, logBytes), trigger }); });
});
const validateSchema = (value, schema) => {
  for (const field of schema.required ?? []) if (!(field in value)) throw new Error(`report schema requires ${field}`);
  for (const [field, rule] of Object.entries(schema.properties ?? {})) {
    if (!(field in value)) continue;
    if ("const" in rule && value[field] !== rule.const) throw new Error(`report schema requires ${field}=${rule.const}`);
    if (rule.enum && !rule.enum.includes(value[field])) throw new Error(`report schema rejects ${field}=${value[field]}`);
  }
};

try {
  beforeMaintained = await hashMaintained();
  const configPath = resolveInside(root, configArgument, "config");
  toolDir = resolveInside(root, toolDirectoryArgument, "tool directory");
  await rejectSymlinkPath(root, configPath); await rejectSymlinkPath(root, toolDir);
  configBytes = await readFile(configPath); config = JSON.parse(configBytes);
  toolchainBytes = await readFile(resolve(root, "xantham/toolchain-lock.json")); toolchain = JSON.parse(toolchainBytes);
  if (config.schemaVersion !== 1) throw new Error("Xantham config schemaVersion must be 1");
  if (process.platform !== "linux" || process.arch !== "x64") throw new Error(`Xantham execution is qualified only for linux-x64; found ${process.platform}-${process.arch}`);
  processRecord.limits = config.limits;
  const cli = resolve(toolDir, "bin/xantham"); const compiler = resolve(toolDir, "compiler", toolchain.compiler.linuxX64Executable);
  const packageRoot = resolve(toolDir, "bin/.store/xantham", toolchain.cli.version, "xantham", toolchain.cli.version);
  const prepared = JSON.parse(await readFile(resolve(toolDir, "prepared.json"), "utf8").catch(() => { throw new Error("Xantham tools are not prepared; run npm run xantham:prepare"); }));
  const packageSha512 = (await readFile(resolve(packageRoot, `xantham.${toolchain.cli.version}.nupkg.sha512`), "utf8")).trim();
  if (await hashFile(cli) !== toolchain.cli.linuxX64ApphostSha256 || prepared.cliApphostSha256 !== toolchain.cli.linuxX64ApphostSha256) throw new Error("Xantham apphost fingerprint does not match the exact qualified pin");
  if (packageSha512 !== toolchain.cli.packageSha512 || prepared.cliPackageSha512 !== toolchain.cli.packageSha512) throw new Error("Xantham package fingerprint does not match the exact qualified pin");
  if (await hashFile(resolve(packageRoot, "tools/net10.0/any/Xantham.Generator.dll")) !== toolchain.cli.generatorAssemblySha256 || prepared.generatorAssemblySha256 !== toolchain.cli.generatorAssemblySha256) throw new Error("Xantham generator assembly fingerprint does not match the exact qualified pin");
  if (await hashFile(compiler) !== toolchain.compiler.linuxX64Sha256 || prepared.compilerSha256 !== toolchain.compiler.linuxX64Sha256) throw new Error("TypeScript compiler fingerprint does not match the exact qualified pin");

  const probeEnv = { ...process.env, HOME: homeDir, XDG_CACHE_HOME: resolve(homeDir, ".cache"), DOTNET_CLI_HOME: resolve(homeDir, ".dotnet"), NUGET_PACKAGES: resolve(root, ".nuget/packages"), XANTHAM_TSGO_EXE: compiler, DOTNET_NOLOGO: "1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE: "1" };
  const cliProbe = await boundedProcess(cli, ["--version"], { cwd: root, env: probeEnv, timeoutMs: 10000, logBytes: config.limits.logBytes });
  const compilerProbe = await boundedProcess(compiler, ["--version"], { cwd: root, env: probeEnv, timeoutMs: 10000, logBytes: config.limits.logBytes });
  if (cliProbe.code !== 0 || cliProbe.trigger) throw new Error(`Xantham version probe failed: ${cliProbe.trigger ?? cliProbe.stderr.toString("utf8")}`);
  if (compilerProbe.code !== 0 || compilerProbe.trigger) throw new Error(`compiler version probe failed: ${compilerProbe.trigger ?? compilerProbe.stderr.toString("utf8")}`);
  cliVersion = cliProbe.stdout.toString("utf8").trim(); compilerVersion = compilerProbe.stdout.toString("utf8").trim().replace(/^Version\s+/, "");
  if (!cliVersion.startsWith(`${toolchain.cli.version}+${toolchain.cli.sourceRevision}`)) throw new Error(`unexpected Xantham version: ${cliVersion}`);
  if (compilerVersion !== toolchain.compiler.version) throw new Error(`unexpected compiler version: ${compilerVersion}`);
  const isolatedCompiler = resolve(homeDir, ".cache/xantham", toolchain.compiler.version, toolchain.compiler.linuxX64Executable);
  await mkdir(resolve(isolatedCompiler, "../../.."), { recursive: true });
  await cp(resolve(compiler, "../.."), resolve(isolatedCompiler, "../.."), { recursive: true });
  if (await hashFile(isolatedCompiler) !== toolchain.compiler.linuxX64Sha256) throw new Error("isolated child-cache compiler fingerprint changed while preparing the run");
  processRecord.compilerCache = { path: relative(root, isolatedCompiler), sha256: toolchain.compiler.linuxX64Sha256 };

  const packageDir = resolveInside(root, config.packageDirectory, "package directory"); const rawConfig = resolveInside(root, config.xanthamConfig, "Xantham config");
  await rejectSymlinkPath(root, packageDir); await rejectSymlinkPath(root, rawConfig);
  if (config.runtimeImport !== config.package.name) throw new Error(`runtime import '${config.runtimeImport}' does not resolve the qualified package '${config.package.name}'`);
  const packageJson = JSON.parse(await readFile(resolve(packageDir, "package.json"), "utf8"));
  if (packageJson.name !== config.package.name || packageJson.version !== config.package.version) throw new Error(`installed package does not match ${config.package.name}@${config.package.version}`);
  const pilotLockPath = resolve(toolDir, "pilot/package-lock.json"); const pilotLock = JSON.parse(await readFile(pilotLockPath, "utf8"));
  if (pilotLock.packages?.[`node_modules/${config.package.name}`]?.integrity !== config.package.integrity) throw new Error("installed pilot package integrity is not the qualified lock entry");
  await import(pathToFileURL(resolve(packageDir, packageJson.exports ?? packageJson.main ?? "index.js"))); verification.imports = "pass";

  const generationStarted = Date.now(); const prlimit = "/usr/bin/prlimit";
  const generatorArgs = [`--as=${config.limits.addressSpaceBytes}`, "--", cli, "generate", packageDir, "-o", rawDir, "--config", rawConfig];
  processRecord.command = [prlimit, ...generatorArgs];
  const generated = await boundedProcess(prlimit, generatorArgs, { cwd: root, env: { ...probeEnv, XANTHAM_TSGO_EXE: isolatedCompiler }, timeoutMs: config.limits.timeoutSeconds * 1000, logBytes: config.limits.logBytes, rssBytes: config.limits.sampledProcessGroupRssBytes, outputDir: rawDir, outputBytes: config.limits.outputBytes });
  phaseDurationsMs.generation = Date.now() - generationStarted; processRecord.exitCode = generated.code; processRecord.signal = generated.signal; processRecord.limitTriggered = generated.trigger;
  await writeFile(resolve(runDir, "stdout.log"), generated.stdout); await writeFile(resolve(runDir, "stderr.log"), generated.stderr);
  verification.limits = generated.trigger ? "fail" : "pass";
  if (generated.trigger) throw new Error(`generation exceeded ${generated.trigger} limit`);
  if (generated.code !== 0) throw new Error(`Xantham exited ${generated.code}: ${generated.stderr.toString("utf8").trim()}`);
  if (await directorySize(rawDir) > config.limits.outputBytes) throw new Error("generated output exceeds configured byte limit");
  ({ manifest } = await validateXanthamCandidate(rawDir, config));
  verification.selectedSymbols = "pass";

  const compileDir = resolve(scratchDir, "compile"); await mkdir(compileDir, { recursive: true }); await cp(resolve(rawDir, "AnsiRegex.fs"), resolve(compileDir, "Generated.fs"));
  await writeFile(resolve(compileDir, "Compile.fsproj"), '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>netstandard2.1</TargetFramework></PropertyGroup><ItemGroup><Compile Include="Generated.fs" /><PackageReference Include="Fable.Core" /></ItemGroup></Project>\n');
  const compileStarted = Date.now();
  const compile = await boundedProcess("dotnet", ["build", resolve(compileDir, "Compile.fsproj"), "--nologo"], { cwd: repositoryRoot, env: probeEnv, timeoutMs: 90000, logBytes: config.limits.logBytes, rssBytes: config.limits.sampledProcessGroupRssBytes });
  phaseDurationsMs.compile = Date.now() - compileStarted; await writeFile(resolve(runDir, "compile.stdout.log"), compile.stdout); await writeFile(resolve(runDir, "compile.stderr.log"), compile.stderr);
  if (compile.code !== 0 || compile.trigger) throw new Error(`generated binding did not compile: ${compile.trigger ?? `${compile.stdout.toString("utf8")}\n${compile.stderr.toString("utf8")}`.trim()}`);
  verification.fsharpCompile = "pass";
  const files = await walkFiles(rawDir); artifactHashes = Object.fromEntries(await Promise.all(files.map(async file => [relative(rawDir, file), await hashFile(file)])));
  const proposalDir = resolve(candidatesRoot, "proposal");
  const proposalInfo = await lstat(proposalDir).catch(error => error.code === "ENOENT" ? null : Promise.reject(error));
  if (proposalInfo?.isSymbolicLink() || (proposalInfo && !proposalInfo.isDirectory())) throw new Error("refusing unsafe Xantham proposal directory");
  status = "proposal-ready";
} catch (error) { diagnostics.push(error.message); }

afterMaintained = await hashMaintained().catch(error => { diagnostics.push(`could not verify maintained workspace: ${error.message}`); return null; });
if (!beforeMaintained || afterMaintained !== beforeMaintained) { diagnostics.push("maintained source, declaration lock, mapping ledger or accepted coverage changed during generation"); status = "rejected"; }
const ended = new Date(); const entryPath = config?.packageDirectory && config?.declarationEntry ? resolve(root, config.packageDirectory, config.declarationEntry) : null;
const report = {
  schemaVersion: 1, runId, startedAt: started.toISOString(), endedAt: ended.toISOString(), phaseDurationsMs, platform: { os: process.platform, architecture: process.arch, node: process.version }, status,
  toolchain: toolchain ? { cli: { ...toolchain.cli, observedVersion: cliVersion }, compiler: { ...toolchain.compiler, observedVersion: compilerVersion }, wire: toolchain.wire, support: toolchain.support, inspectedUpstreamRevision: toolchain.inspectedUpstreamRevision } : null,
  input: config ? { package: config.package, npmLockSha256: toolDir ? await hashFile(resolve(toolDir, "pilot/package-lock.json")).catch(() => null) : null, declarationEntry: config.declarationEntry, declarationEntrySha256: entryPath ? await hashFile(entryPath).catch(() => null) : null, runtimeImport: config.runtimeImport, fsharpModule: config.fsharpModule, selectedSignatures: config.selectedSignatures, configSha256: sha256(configBytes), toolchainLockSha256: sha256(toolchainBytes) } : null,
  process: processRecord, artifacts: { runDirectory: relative(root, runDir), rawDirectory: relative(root, rawDir), hashes: artifactHashes }, findings: { counts: manifest?.counts ?? null, lossDispositions: config?.lossDispositions ?? [] },
  maintainedEvidence: config ? Object.fromEntries(await Promise.all(config.maintainedEvidence.map(async path => [path, await hashFile(resolve(root, path)).catch(() => null)]))) : {}, verification,
  maintainedWorkspace: { beforeSha256: beforeMaintained, afterSha256: afterMaintained, unchanged: Boolean(beforeMaintained && beforeMaintained === afterMaintained) }, diagnostics
};
try { validateSchema(report, JSON.parse(await readFile(resolve(root, "xantham/schemas/run-report.schema.json"), "utf8"))); verification.reportSchema = "pass"; }
catch (error) { verification.reportSchema = "fail"; diagnostics.push(error.message); status = "rejected"; report.status = status; }
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);

if (status === "proposal-ready") {
  const proposalDir = resolve(candidatesRoot, "proposal");
  await mkdir(proposalDir, { recursive: true });
  for (const name of ["AnsiRegex.fs", "manifest.json", "symbols.jsonl"]) { const temp = resolve(proposalDir, `.${name}.${runId}`); await cp(resolve(rawDir, name), temp); await rename(temp, resolve(proposalDir, name)); }
}
console.log(`${status}: ${relative(root, reportPath)}`);
if (status !== "proposal-ready") { console.error(diagnostics.join("\n")); process.exitCode = 1; }
