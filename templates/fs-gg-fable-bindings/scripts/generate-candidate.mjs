import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
const lock = await readFile(resolve(root, "declaration-lock.json"));
const digest = createHash("sha256").update(lock).digest("hex");
await mkdir(resolve(root, "generated-candidates"), { recursive: true });
await writeFile(resolve(root, "generated-candidates", "BabylonBindings.generated.fs"), `// GENERATED CANDIDATE — NOT COMPILED, PACKED, OR PUBLIC\n// declaration closure SHA-256: ${digest}\n// Review into src/BabylonBindings.fs; never overwrite maintained bindings.\nmodule Qualification.Candidate\n\ntype UnsupportedTypeScriptConstruct = obj\n`);
await writeFile(resolve(root, "generated-candidates", "BabylonBindings.proposal.md"), `# Generated candidate proposal\n\nInput declaration closure SHA-256: \`${digest}\`\n\nThis tracked artifact is the reviewable generated proposal. Compare it with \`../src/BabylonBindings.fs\`; the generator never writes maintained source or the lock.\n`);
console.log("updated tracked review proposal only")
