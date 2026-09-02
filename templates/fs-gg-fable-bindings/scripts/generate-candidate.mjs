import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");
const lockBytes = await readFile(resolve(root, "declaration-lock.json"));
const lock = JSON.parse(lockBytes);
const digest = createHash("sha256").update(lockBytes).digest("hex");
const candidates = resolve(root, "generated-candidates");

const hazardKinds = new Map([
  [ts.SyntaxKind.ConditionalType, "conditionalTypes"],
  [ts.SyntaxKind.MappedType, "mappedTypes"],
  [ts.SyntaxKind.TemplateLiteralType, "templateLiteralTypes"],
  [ts.SyntaxKind.IndexSignature, "indexSignatures"],
  [ts.SyntaxKind.InferType, "inferredTypes"]
]);
const hazardCounts = Object.fromEntries([...hazardKinds.values()].map(name => [name, 0]));
const declarations = new Map();
const bareImports = new Set();

const addDeclaration = (name, path) => {
  if (!name) return;
  const paths = declarations.get(name) ?? new Set();
  paths.add(path);
  declarations.set(name, paths);
};

for (const { path } of lock.files) {
  const sourceText = await readFile(resolve(root, "node_modules", path), "utf8");
  const source = ts.createSourceFile(path, sourceText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const preprocessed = ts.preProcessFile(sourceText, true, true);
  for (const imported of preprocessed.importedFiles) {
    if (!imported.fileName.startsWith(".")) bareImports.add(imported.fileName);
  }
  const visit = node => {
    const hazard = hazardKinds.get(node.kind);
    if (hazard) hazardCounts[hazard] += 1;
    if (ts.isInterfaceDeclaration(node) || ts.isClassDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isEnumDeclaration(node) || (ts.isModuleDeclaration(node) && ts.isIdentifier(node.name))) {
      addDeclaration(node.name?.getText(source), path);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}

const mergedDeclarations = [...declarations]
  .filter(([, paths]) => paths.size > 1)
  .map(([symbol, paths]) => ({ symbol, files: [...paths].sort() }))
  .sort((left, right) => left.symbol.localeCompare(right.symbol));
const analysis = {
  schemaVersion: 1,
  declarationClosureSha256: digest,
  declarationFileCount: lock.files.length,
  hazardCounts,
  declarationMergingCandidates: mergedDeclarations,
  bareModuleReferences: [...bareImports].sort(),
  interpretation: "Counts identify manual review pressure; they are not typed-coverage claims."
};

const hazardLines = Object.entries(hazardCounts).map(([name, count]) => `| ${name} | ${count} |`).join("\n");
const topMerged = mergedDeclarations.slice(0, 20);
const mergeLines = topMerged.length === 0
  ? "No cross-file declaration-merging candidates detected."
  : topMerged.map(row => `- \`${row.symbol}\` — ${row.files.length} declaration files`).join("\n");

await mkdir(candidates, { recursive: true });
await writeFile(resolve(candidates, "declaration-analysis.json"), `${JSON.stringify(analysis, null, 2)}\n`);
await writeFile(resolve(candidates, "BabylonBindings.generated.fs"), `// GENERATED CANDIDATE — NOT COMPILED, PACKED, OR PUBLIC
// declaration closure SHA-256: ${digest}
// Review the analysis and mapping ledger before curating src/BindingsProduct/Bindings.fs.
module Qualification.Candidate

// This intentionally contains no public binding guesses. Generation inventories risk;
// maintained source owns F# names, file boundaries, imports, nullability and overloads.
`);
await writeFile(resolve(candidates, "BabylonBindings.proposal.md"), `# Generated candidate proposal

Input declaration closure SHA-256: \`${digest}\`

The generator inspected ${lock.files.length} locked declaration files with the TypeScript parser. It
writes review inputs only and never changes maintained bindings, \`binding-plan.json\`, or the lock.

## Construct pressure

| Construct | Occurrences |
| --- | ---: |
${hazardLines}

## Cross-file declaration-merging candidates

${mergeLines}

Use \`declaration-analysis.json\` for the complete machine-readable inventory. Review strongly
connected/merged types as subsystem units, then update the mapping ledger and curate only the next
executable slice into \`src/BindingsProduct/Bindings.fs\`.
`);
console.log("updated tracked analysis and review proposal only");
