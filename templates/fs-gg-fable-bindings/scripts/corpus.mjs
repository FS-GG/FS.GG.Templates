import { readFile } from "node:fs/promises";

// One declaration corpus: exact npm artifacts, selected declaration entry points and the
// candidate file stem. Adding a corpus means writing this file, curated source and runtime
// smoke; the lock and candidate scripts carry no corpus-specific values.
export const loadCorpus = async path => {
  const corpus = JSON.parse(await readFile(path, "utf8"));
  const exact = /^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$/;
  if (corpus.schemaVersion !== 1) throw new Error(`${path}: unsupported corpus schemaVersion ${corpus.schemaVersion}`);
  if (typeof corpus.id !== "string" || !/^[a-z0-9][a-z0-9-]*$/.test(corpus.id)) throw new Error(`${path}: corpus id must be a lowercase slug`);
  if (!Array.isArray(corpus.npmArtifacts) || corpus.npmArtifacts.length === 0) throw new Error(`${path}: npmArtifacts must list at least one exact artifact`);
  for (const artifact of corpus.npmArtifacts) {
    if (typeof artifact?.name !== "string" || !exact.test(artifact?.version ?? "")) throw new Error(`${path}: npm artifact ${JSON.stringify(artifact)} is not an exact name/version pin`);
  }
  if (!Array.isArray(corpus.declarationEntryPoints) || corpus.declarationEntryPoints.length === 0) throw new Error(`${path}: declarationEntryPoints must be non-empty`);
  const names = corpus.npmArtifacts.map(artifact => artifact.name);
  for (const entry of corpus.declarationEntryPoints) {
    if (typeof entry !== "string" || !entry.endsWith(".d.ts") || !names.some(name => entry.startsWith(`${name}/`))) throw new Error(`${path}: entry point ${JSON.stringify(entry)} is not a .d.ts file inside a pinned artifact`);
  }
  if (typeof corpus.candidateStem !== "string" || !/^[A-Z][A-Za-z0-9]*$/.test(corpus.candidateStem)) throw new Error(`${path}: candidateStem must be a PascalCase identifier`);
  return corpus;
};

// Lock identity fields. Schema 2 keeps `package`/`companionPackage` so an existing
// two-artifact lock is byte-identical; a larger closure lists the rest in order.
export const lockIdentity = corpus => {
  const [primary, ...rest] = corpus.npmArtifacts.map(artifact => `${artifact.name}@${artifact.version}`);
  if (rest.length === 0) return { package: primary };
  if (rest.length === 1) return { package: primary, companionPackage: rest[0] };
  return { package: primary, companionPackages: rest };
};
