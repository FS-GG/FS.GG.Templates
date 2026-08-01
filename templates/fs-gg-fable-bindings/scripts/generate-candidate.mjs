import { mkdirSync, writeFileSync } from "node:fs";
mkdirSync(new URL("../generated-candidates", import.meta.url), { recursive: true });
writeFileSync(new URL("../generated-candidates/candidate.md", import.meta.url), "# Candidate\n\nGenerated output is a review proposal. It must not overwrite src/ or declaration-lock.json.\n");
