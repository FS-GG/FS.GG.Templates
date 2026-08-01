import { existsSync, readFileSync } from "node:fs";
for (const file of ["package-lock.json", "declaration-lock.json", "coverage-and-drift.json", "scaffold-provenance.json", ".fsgg/bindings-evidence.yml"]) if (!existsSync(file)) throw new Error(`missing required evidence artifact: ${file}`);
const provenance = JSON.parse(readFileSync("scaffold-provenance.json"));
if (provenance.activation !== "not-published-or-registry-active") throw new Error("publication/activation boundary is invalid");
console.log("fable-bindings doctor passed: local proof remains required before publication")
