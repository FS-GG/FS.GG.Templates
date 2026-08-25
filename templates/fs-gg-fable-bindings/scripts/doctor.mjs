import { existsSync, readFileSync } from "node:fs";
// The two `packages.lock.json` entries are FS.GG.Templates#384. They are listed HERE, and not only
// in `build.sh`, because `npm run doctor` is the one in-template check the required composition lane
// actually runs before its `dotnet restore --locked-mode`. That matters: the whole defect is that a
// locked restore with no lock on disk does not fail — it AUTHORS one from the ambient machine and
// then enforces it — so a lane that restores first and asks questions later cannot observe the
// missing delivery at all. `dotnet new` strips `**/*.lock.json` by default, which is exactly how two
// reviewed locks were committed here and zero reached any generated product while every gate stayed
// green. `BindingsProduct` is rewritten to the product's name on instantiation, as in
// `lifecycle-evidence.mjs`, so these paths name the delivered projects rather than the template's.
for (const file of ["package-lock.json", "declaration-lock.json", "coverage-and-drift.json", "scaffold-provenance.json", "bindings-evidence.yml", "src/BindingsProduct/packages.lock.json", "tests/BindingsProduct.CompileTests/packages.lock.json"]) if (!existsSync(file)) throw new Error(`missing required evidence artifact: ${file}`);
const provenance = JSON.parse(readFileSync("scaffold-provenance.json"));
if (provenance.activation !== "not-published-or-registry-active") throw new Error("publication/activation boundary is invalid");
console.log("fable-bindings doctor passed: local proof remains required before publication")
