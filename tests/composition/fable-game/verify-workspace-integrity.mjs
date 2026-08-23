import { cpSync, existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const workspace = resolve(process.argv[2] ?? "templates/fs-gg-fable-game");
const solutionPath = readdirSync(workspace).filter((path) => path.endsWith(".slnx"));
const fail = (message) => { throw new Error(`workspace integrity: ${message}`); };
const read = (path) => readFileSync(join(workspace, path), "utf8");
const required = (path) => {
  if (!existsSync(join(workspace, path))) fail(`missing required shipped file ${path}`);
};
const references = (xml) => [...xml.matchAll(/<ProjectReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["']/gi)].map((match) => match[1]);

const projects = [
  "Domain/Domain.fsproj", "Domain.Tests/Domain.Tests.fsproj", "Protocol/Protocol.fsproj",
  "Protocol.Tests/Protocol.Tests.fsproj", "Server/Server.fsproj", "Server.Tests/Server.Tests.fsproj"
];
const allProjects = [...projects, "Client/Client.fsproj"];
const locks = [
  "Domain/packages.lock.json", "Domain.Tests/packages.lock.json", "Protocol/packages.lock.json",
  "Protocol.Tests/packages.lock.json", "Server/packages.lock.json", "Server.Tests/packages.lock.json",
  "Client/packages.lock.json", "Protocol.Tests/cross-runtime/CodecProbe.Net/packages.lock.json",
  "Protocol.Tests/cross-runtime/CodecProbe.Fable/packages.lock.json", "Client/package-lock.json",
  "Browser.Tests/package-lock.json", ".config/dotnet-tools.json"
];
const npmRoots = ["Client", "Browser.Tests"];

const auditNpmRoots = (run = spawnSync) => {
  for (const root of npmRoots) {
    const result = run("npm", ["audit", "--package-lock-only", "--omit=dev", "--audit-level=high"], {
      cwd: join(workspace, root), stdio: "inherit"
    });
    if (result.status !== 0) fail(`production npm audit failed for ${root} (exit ${result.status ?? "unavailable"})`);
  }
};

const validate = (input) => {
  for (const path of locks) input.required(path);
  if (solutionPath.length !== 1) fail(`workspace must ship exactly one solution file (found ${solutionPath.length})`);
  const solution = input.read(solutionPath[0]);
  for (const path of projects) {
    if (!solution.includes(`Project Path=\"${path}\"`)) fail(`solution omits ${path}`);
  }
  if (solution.includes('Project Path="Client/Client.fsproj"')) fail("solution must not compile the Fable client through dotnet build");

  const server = input.read("Server/Server.fsproj");
  const client = input.read("Client/Client.fsproj");
  const serverReferences = references(server).join(" ");
  if (!serverReferences.includes("../Domain/Domain.fsproj") || !serverReferences.includes("../Protocol/Protocol.fsproj"))
    fail("Server lacks the Domain/Protocol authority boundary");
  const projectReferences = (project) => references(input.read(project)).map((reference) =>
    relative(workspace, resolve(workspace, dirname(project), reference)).replaceAll("\\", "/"));
  const serverClosure = new Set();
  const visitServerDependency = (project) => {
    if (serverClosure.has(project)) return;
    if (!allProjects.includes(project)) fail(`Server dependency closure reaches unknown project ${project}`);
    serverClosure.add(project);
    for (const dependency of projectReferences(project)) visitServerDependency(dependency);
  };
  visitServerDependency("Server/Server.fsproj");
  if (serverClosure.has("Client/Client.fsproj")) fail("Server dependency closure reaches forbidden Fable Client project");
  for (const project of serverClosure) {
    const packages = [...input.read(project).matchAll(/<PackageReference\b[^>]*\bInclude\s*=\s*["']([^"']+)["']/gi)].map((match) => match[1]);
    if (packages.some((packageName) => /^Fable(?:\.|$)/i.test(packageName)))
      fail(`Server dependency closure includes forbidden Fable package through ${project}`);
  }
  if (references(client).length !== 0) fail("Fable Client must not carry ProjectReference edges");
  for (const shared of ["../Protocol/Http.fs", "../Protocol/Realtime.fs"]) {
    if (!client.includes(`Compile Include=\"${shared}\"`)) fail(`Fable Client lacks shared wire source ${shared}`);
  }
  if (!input.read("Domain.Tests/Domain.Tests.fsproj").includes("../Domain/Domain.fsproj")) fail("Domain.Tests lacks Domain edge");
  if (!input.read("Protocol.Tests/Protocol.Tests.fsproj").includes("../Protocol/Protocol.fsproj")) fail("Protocol.Tests lacks Protocol edge");
  if (!input.read("Server.Tests/Server.Tests.fsproj").includes("../Server/Server.fsproj")) fail("Server.Tests lacks Server edge");

  const global = JSON.parse(input.read("global.json"));
  const tools = JSON.parse(input.read(".config/dotnet-tools.json"));
  if (global.sdk?.version !== "10.0.400" || global.sdk?.rollForward !== "latestFeature") fail("global.json SDK pin is not the supported exact toolchain metadata");
  if (tools.tools?.fable?.version !== "5.13.0" || !tools.tools.fable.commands?.includes("fable")) fail("dotnet tool manifest lacks the exact Fable tool pin");
  const clientPackage = JSON.parse(input.read("Client/package.json"));
  const browserPackage = JSON.parse(input.read("Browser.Tests/package.json"));
  const clientLock = JSON.parse(input.read("Client/package-lock.json"));
  const browserLock = JSON.parse(input.read("Browser.Tests/package-lock.json"));
  const coherentLock = (name, manifest, lock) => lock.lockfileVersion === 3 && lock.packages?.[""]?.name === manifest.name && JSON.stringify(lock.packages[""]?.dependencies ?? {}) === JSON.stringify(manifest.dependencies ?? {}) && JSON.stringify(lock.packages[""]?.devDependencies ?? {}) === JSON.stringify(manifest.devDependencies ?? {});
  if (!coherentLock("Client", clientPackage, clientLock)) fail("Client package manifest and lockfile are incoherent");
  if (!coherentLock("Browser.Tests", browserPackage, browserLock)) fail("Browser.Tests package manifest and lockfile are incoherent");
  if (clientPackage.dependencies?.["@microsoft/signalr"] !== "10.0.0" || clientPackage.devDependencies?.vite !== "7.1.3" || browserPackage.devDependencies?.["@playwright/test"] !== "1.55.0") fail("npm toolchain pins are not exact and coherent");
};

const input = { read, required };
validate(input);

const mutateAndExpect = (path, mutate, expected) => {
  const original = read(path);
  const mutated = new Map([[path, mutate(original)]]);
  const mutant = { read: (requested) => mutated.get(requested) ?? read(requested), required };
  try { validate(mutant); fail(`${basename(path)} mutation survived`); }
  catch (error) { if (!String(error.message).includes(expected)) throw error; }
};

if (process.argv.includes("--self-test")) {
  mutateAndExpect("Server/Server.fsproj", (source) => `${source}\n<ProjectReference Include=\"../Client/Client.fsproj\" />`, "Server dependency closure reaches forbidden Fable Client project");
  mutateAndExpect("Domain/Domain.fsproj", (source) => `${source}\n<ItemGroup><ProjectReference Include=\"../Client/Client.fsproj\" /></ItemGroup>`, "Server dependency closure reaches forbidden Fable Client project");
  mutateAndExpect("Domain/Domain.fsproj", (source) => `${source}\n<ItemGroup><PackageReference Include=\"Fable.Core\" Version=\"[5.2.0]\" /></ItemGroup>`, "Server dependency closure includes forbidden Fable package through Domain/Domain.fsproj");
  mutateAndExpect(solutionPath[0], (source) => source.replace('Project Path="Protocol/Protocol.fsproj"', 'Project Path="Protocol/Removed.fsproj"'), "solution omits Protocol/Protocol.fsproj");
  mutateAndExpect("Client/package-lock.json", (source) => source.replace('"lockfileVersion": 3', '"lockfileVersion": 2'), "Client package manifest and lockfile are incoherent");

  for (const [missing, diagnostic] of [["Client/package-lock.json", "missing: Client/package-lock.json"], ["Browser.Tests/package-lock.json", "missing: Browser.Tests/package-lock.json"], [".config/dotnet-tools.json", "workspace shipped without .config/dotnet-tools.json"]]) {
    const temporary = mkdtempSync(join(tmpdir(), "fs-gg-workspace-precondition-"));
    const copy = join(temporary, "workspace");
    cpSync(workspace, copy, { recursive: true });
    rmSync(join(copy, missing));
    const result = spawnSync("bash", ["./build.sh"], { cwd: copy, encoding: "utf8" });
    rmSync(temporary, { recursive: true, force: true });
    if (result.status === 0 || !result.stderr.includes(diagnostic)) fail(`missing ${missing} did not fail with its owning build.sh diagnostic`);
  }

  for (const rejectedRoot of npmRoots) {
    const observed = [];
    let rejected = false;
    try {
      auditNpmRoots((_command, _arguments, options) => {
        const root = basename(options.cwd);
        observed.push(root);
        return { status: root === rejectedRoot ? 42 : 0 };
      });
    } catch (error) {
      if (!String(error.message).includes(`production npm audit failed for ${rejectedRoot} (exit 42)`)) throw error;
      rejected = true;
    }
    if (!rejected || !observed.includes(rejectedRoot)) fail(`${rejectedRoot} npm audit failure mutation survived`);
  }
  console.log("workspace integrity self-test: graph, lock coherence, shipped-prerequisite, and per-root npm-audit mutations rejected");
}

if (process.argv.includes("--audit")) auditNpmRoots();

console.log(`workspace integrity verified: ${workspace}`);
