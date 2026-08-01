import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

// Glutinum.Template@1.1.1 is a comparison input, not a public-API writer.
const root = resolve(import.meta.dirname, "..");
const candidate = resolve(root, "generated-candidates", "BabylonBindings.generated.fs");
await mkdir(resolve(root, "generated-candidates"), { recursive: true });
await writeFile(candidate, `// GENERATED CANDIDATE — NOT COMPILED, PACKED, OR PUBLIC\n// Review into src/BabylonBindings.fs; never overwrite maintained bindings.\nnamespace Qualification.Candidate\n\ntype UnsupportedTypeScriptConstruct = obj\n`);
console.log(`proposed ${candidate}; maintained src/ was not modified`);
