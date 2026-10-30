import { existsSync, readFileSync } from "node:fs";
import { loadCorpus, lockIdentity } from "./corpus.mjs";
// The two `packages.lock.json` entries are FS.GG.Templates#384. They are listed HERE, and not only
// in `build.sh`, because `npm run doctor` is the one in-template check the required composition lane
// actually runs before its `dotnet restore --locked-mode`. That matters: the whole defect is that a
// locked restore with no lock on disk does not fail — it AUTHORS one from the ambient machine and
// then enforces it — so a lane that restores first and asks questions later cannot observe the
// missing delivery at all. `dotnet new` strips `**/*.lock.json` by default, which is exactly how two
// reviewed locks were committed here and zero reached any generated product while every gate stayed
// green. `BindingsProduct` is rewritten to the product's name on instantiation, as in
// `lifecycle-evidence.mjs`, so these paths name the delivered projects rather than the template's.
for (const file of ["corpus.json", "package-lock.json", ".config/dotnet-tools.json", "declaration-lock.json", "binding-plan.json", "coverage-and-drift.json", "generated-candidates/declaration-analysis.json", "scaffold-provenance.json", "bindings-evidence.yml", "xantham/toolchain-lock.json", "xantham/release-assessments.json", "xantham/ansi-regex.json", "xantham/ansi-regex.xantham.json", "xantham/compiler/package-lock.json", "xantham/schemas/run-report.schema.json", "xantham/schemas/update-assessment.schema.json", "src/BindingsProduct/packages.lock.json", "tests/BindingsProduct.CompileTests/packages.lock.json"]) if (!existsSync(file)) throw new Error(`missing required evidence artifact: ${file}`);
const provenance = JSON.parse(readFileSync("scaffold-provenance.json"));
if (provenance.activation !== "not-published-or-registry-active") throw new Error("publication/activation boundary is invalid");
const plan = JSON.parse(readFileSync("binding-plan.json"));
const coverage = JSON.parse(readFileSync("coverage-and-drift.json"));
if (!plan.slice?.journey || plan.mappingLedger?.length === 0) throw new Error("binding plan has no executable slice or mapping ledger");
if (coverage.bindingPlan !== "binding-plan.json" || coverage.schemaVersion < 2) throw new Error("coverage report is not bound to the advanced mapping plan");
if (plan.mappingLedger.some(row => row.coverage === "dynamic") && coverage.typedCoverage.includes(plan.mappingLedger.find(row => row.coverage === "dynamic")?.symbol)) throw new Error("dynamic escape hatch counted as typed coverage");
// corpus.json is the one declaration of the npm closure. The workspace files that also name it
// (package.json, the binding project's Femto <NpmDependencies>, scaffold provenance, and the
// declaration lock) must agree with it, as must the binding plan's runtime entry points. The
// template's own parameter choices live outside a generated workspace; the composition lane
// checks those against the template's corpus.json.
const corpus = await loadCorpus("corpus.json");
const pinned = corpus.npmArtifacts.map(({ name, version }) => `${name}@${version}`);
const dependencies = JSON.parse(readFileSync("package.json")).dependencies ?? {};
if (JSON.stringify(Object.entries(dependencies).map(([name, version]) => `${name}@${version}`).sort()) !== JSON.stringify([...pinned].sort())) throw new Error(`package.json dependencies differ from corpus.json npmArtifacts (${pinned.join(", ")})`);
const bindingProject = readFileSync("src/BindingsProduct/BindingsProduct.fsproj", "utf8");
const femto = [...bindingProject.matchAll(/<NpmPackage\s+Name="([^"]+)"\s+Version="([^"]+)"\s*\/>/g)].map(([, name, version]) => `${name}@${version}`);
if (JSON.stringify(femto.sort()) !== JSON.stringify([...pinned].sort())) throw new Error(`binding project <NpmDependencies> (${femto.join(", ")}) differ from corpus.json npmArtifacts (${pinned.join(", ")}); the packed NuGet package would declare a different npm runtime`);
if (JSON.stringify(provenance.npmClosure) !== JSON.stringify(pinned)) throw new Error("scaffold-provenance.json npmClosure differs from corpus.json npmArtifacts");
const lock = JSON.parse(readFileSync("declaration-lock.json"));
const identity = lockIdentity(corpus);
if (Object.keys(identity).some(key => JSON.stringify(lock[key]) !== JSON.stringify(identity[key])) || JSON.stringify(lock.entryPoints) !== JSON.stringify(corpus.declarationEntryPoints)) throw new Error("declaration-lock.json was not produced from corpus.json; run npm run lock:declarations and review");
if (!plan.slice.entryPoints.every(entry => corpus.npmArtifacts.some(({ name }) => entry === name || entry.startsWith(`${name}/`)))) throw new Error("binding-plan.json runtime entry point is outside the corpus npm artifacts");
// The template parameters choose which corpus is delivered; the pair the product asked for is
// written into provenance at instantiation. An unfilled placeholder means the file was not
// instantiated (the template source itself), which is not a mismatch.
const requested = provenance.requestedCorpus ?? {};
const [primary] = corpus.npmArtifacts;
for (const [key, expected] of [["npmPackage", primary.name], ["npmVersion", primary.version]]) {
  if (typeof requested[key] !== "string") throw new Error(`scaffold-provenance.json requestedCorpus.${key} is missing`);
  if (!requested[key].startsWith("@@") && requested[key] !== expected) throw new Error(`the product asked for ${key} ${requested[key]}, but the delivered corpus is ${primary.name}@${primary.version}; regenerate with a matching --npmPackage/--npmVersion pair`);
}
// Declarations of modules outside the pinned artifacts are recorded in the lock, not hashed. Each
// needs an explicit curation row, and a package row must match the exact version and integrity
// npm locked, so a moved external dependency is a reviewed change.
const curated = new Map((coverage.externalModules ?? []).map(row => [row.module, row]));
const locked = lock.externalModules ?? [];
if (JSON.stringify([...curated.keys()].sort()) !== JSON.stringify([...locked].sort())) throw new Error(`coverage-and-drift.json externalModules (${[...curated.keys()].join(", ")}) differ from the declaration lock's externalModules (${locked.join(", ")}); curate each recorded external module`);
const packages = JSON.parse(readFileSync("package-lock.json")).packages ?? {};
for (const [module, row] of curated) {
  if (row.decision !== "recorded-not-followed" || typeof row.reason !== "string" || row.reason.length === 0) throw new Error(`external module ${module} needs decision "recorded-not-followed" and a reason`);
  if (module.startsWith("*")) {
    if ("version" in row || "integrity" in row) throw new Error(`ambient pattern ${module} is not a package and must not carry a version`);
    continue;
  }
  const installed = packages[`node_modules/${module}`];
  if (installed?.version !== row.version || installed?.integrity !== row.integrity) throw new Error(`external module ${module} is curated at ${row.version} but package-lock.json locks ${installed?.version}; review the new declarations and update the curation row`);
}
console.log("fable-bindings doctor passed: local proof remains required before publication")
