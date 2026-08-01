import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

// Glutinum.Template@1.1.1 is a comparison input, not a public-API writer.
const root = resolve(import.meta.dirname, "..");
const candidate = resolve(root, "generated-candidates", "BabylonBindings.generated.fs");
const proposal = resolve(root, "generated-candidates", "BabylonBindings.proposal.md");
const lock = await readFile(resolve(root, "declaration-lock.json"));
const closureHash = createHash("sha256").update(lock).digest("hex");
await mkdir(resolve(root, "generated-candidates"), { recursive: true });
await writeFile(candidate, `// GENERATED CANDIDATE — NOT COMPILED, PACKED, OR PUBLIC\n// declaration closure SHA-256: ${closureHash}\n// Review into src/BabylonBindings.fs; never overwrite maintained bindings.\nmodule Qualification.Candidate\n\ntype UnsupportedTypeScriptConstruct = obj\n`);
await writeFile(proposal, `# Generated candidate proposal\n\nInput declaration closure SHA-256: \`${closureHash}\`\n\nThis tracked artifact is the reviewable generated proposal. Compare it with\n\`../src/BabylonBindings.fs\` and carry only reviewed, curated changes into the\npublic surface. The generator never writes maintained source or the lock.\n`);
console.log(`proposed tracked candidate and review note; maintained src/ was not modified`);
