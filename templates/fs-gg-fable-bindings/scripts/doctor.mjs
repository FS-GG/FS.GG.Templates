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
// One corpus declaration drives the lock; every other place naming the npm closure must agree with it.
const corpus = await loadCorpus("corpus.json");
const pinned = corpus.npmArtifacts.map(({ name, version }) => `${name}@${version}`);
const dependencies = JSON.parse(readFileSync("package.json")).dependencies ?? {};
if (JSON.stringify(Object.entries(dependencies).map(([name, version]) => `${name}@${version}`).sort()) !== JSON.stringify([...pinned].sort())) throw new Error(`package.json dependencies differ from corpus.json npmArtifacts (${pinned.join(", ")})`);
if (JSON.stringify(provenance.npmClosure) !== JSON.stringify(pinned)) throw new Error("scaffold-provenance.json npmClosure differs from corpus.json npmArtifacts");
const lock = JSON.parse(readFileSync("declaration-lock.json"));
const identity = lockIdentity(corpus);
if (Object.keys(identity).some(key => JSON.stringify(lock[key]) !== JSON.stringify(identity[key])) || JSON.stringify(lock.entryPoints) !== JSON.stringify(corpus.declarationEntryPoints)) throw new Error("declaration-lock.json was not produced from corpus.json; run npm run lock:declarations and review");
if (!plan.slice.entryPoints.every(entry => corpus.npmArtifacts.some(({ name }) => entry.startsWith(`${name}/`)))) throw new Error("binding-plan.json runtime entry point is outside the corpus npm artifacts");
console.log("fable-bindings doctor passed: local proof remains required before publication")
