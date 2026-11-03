import { createHash } from "node:crypto";
import { readFile, stat, writeFile } from "node:fs/promises";
import { dirname, extname, normalize, relative, resolve } from "node:path";
import { ast as ts, createDeclarationParser } from "./declaration-parser.mjs";
import { loadCorpus, lockIdentity } from "./corpus.mjs";

const args = process.argv.slice(2);
const valueAfter = flag => {
  const index = args.indexOf(flag);
  return index < 0 ? undefined : args[index + 1];
};
const root = resolve(valueAfter("--declarations-root") ?? resolve(import.meta.dirname, "..", "node_modules"));
const lockPath = resolve(valueAfter("--lock") ?? resolve(import.meta.dirname, "..", "declaration-lock.json"));
const corpus = await loadCorpus(resolve(valueAfter("--corpus") ?? resolve(import.meta.dirname, "..", "corpus.json")));
const entryPoints = valueAfter("--entry") ? [valueAfter("--entry")] : corpus.declarationEntryPoints;
// The closure is labelled with the corpus pins, so the installed artifacts must be exactly those.
if (!valueAfter("--entry")) {
  for (const { name, version } of corpus.npmArtifacts) {
    const installed = JSON.parse(await readFile(resolve(root, name, "package.json"), "utf8")).version;
    if (installed !== version) throw new Error(`installed ${name}@${installed} differs from corpus pin ${version}; run npm ci or review the corpus`);
  }
}
// Bare specifiers are followed only into the pinned artifacts; with --entry, into the entry's package.
const followedPackages = valueAfter("--entry") ? [packageOf(valueAfter("--entry")).name] : corpus.npmArtifacts.map(artifact => artifact.name);

const isFile = async path => {
  try {
    return (await stat(path)).isFile();
  } catch (error) {
    if (error.code === "ENOENT" || error.code === "ENOTDIR") return false;
    throw error;
  }
};
const inRoot = path => {
  if (!path.startsWith(`${root}/`)) throw new Error(`declaration reference escaped root: ${path}`);
  return relative(root, path).replaceAll("\\", "/");
};
function packageOf(specifier) {
  const parts = specifier.split("/");
  const count = specifier.startsWith("@") ? 2 : 1;
  return { name: parts.slice(0, count).join("/"), subpath: parts.slice(count).join("/") };
}

// Declaration files TypeScript would read for a requested module path: an explicit
// declaration, the declaration twin of a JavaScript file, or an extensionless file or folder.
const declarationCandidates = requested => {
  if (/\.d\.[mc]?ts$/.test(requested)) return [requested];
  const javascript = requested.match(/\.([mc]?)jsx?$/);
  if (javascript) return [`${requested.slice(0, -javascript[0].length)}.d.${javascript[1]}ts`];
  return [`${requested}.d.ts`, `${requested}/index.d.ts`];
};
// A module path that has no declaration and carries a bundler-asset extension (shaders,
// styles, data, media) is recorded, never read or hashed. The list is explicit: any other
// dotted name that does not resolve is an error, not a silently omitted file.
const assetExtensions = new Set([
  ".frag", ".vert", ".wgsl", ".glsl", ".fx", ".css", ".scss", ".sass", ".less", ".json",
  ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ktx", ".ktx2", ".dds", ".env", ".hdr",
  ".glb", ".gltf", ".bin", ".wasm", ".txt", ".html"
]);
const isAssetPath = requested => assetExtensions.has(extname(requested).toLowerCase());

const assets = new Set();
const external = new Set();
const resolvePath = async (requested, from, specifier) => {
  for (const candidate of declarationCandidates(requested)) {
    if (await isFile(candidate)) return inRoot(candidate);
  }
  if (isAssetPath(requested)) {
    assets.add(inRoot(requested));
    return undefined;
  }
  throw new Error(`unresolved declaration reference: ${from} -> ${specifier}`);
};
const packageTypes = async name => {
  const manifestPath = resolve(root, name, "package.json");
  const manifest = (await isFile(manifestPath)) ? JSON.parse(await readFile(manifestPath, "utf8")) : {};
  return resolve(root, name, manifest.types ?? manifest.typings ?? "index.d.ts");
};
const resolveModule = async (from, specifier) => {
  if (/^\.\.?(?:\/|$)/.test(specifier)) {
    return resolvePath(inRootPath(resolve(dirname(resolve(root, from)), specifier)), from, specifier);
  }
  const { name, subpath } = packageOf(specifier);
  if (!followedPackages.includes(name)) {
    external.add(name);
    return undefined;
  }
  return resolvePath(subpath === "" ? await packageTypes(name) : resolve(root, name, subpath), from, specifier);
};
const resolveTypes = async (from, name) => {
  if (!followedPackages.includes(packageOf(name).name)) {
    external.add(packageOf(name).name);
    return undefined;
  }
  return resolveModule(from, name);
};
const inRootPath = path => {
  const normalized = normalize(path);
  inRoot(normalized);
  return normalized;
};

// Module specifiers are read from the syntax tree, including namespace exports.
// A node that carries a module reference
// in a form this scanner does not follow is an error, never a silent omission.
const moduleSpecifiers = (path, source) => {
  const found = new Set();
  const take = (node, literal) => {
    if (literal === undefined || !ts.isStringLiteralLikeNode(literal)) {
      throw new Error(`${path}: unsupported module specifier syntax (${ts.SyntaxKind[node.kind]}) at offset ${node.getStart(source)}`);
    }
    found.add(literal.text);
  };
  const visit = node => {
    if (node.moduleSpecifier !== undefined) take(node, node.moduleSpecifier); // import / export declarations
    else if (ts.isExternalModuleReference(node)) take(node, node.expression); // import x = require("m")
    else if (ts.isImportTypeNode(node)) take(node, ts.isLiteralTypeNode(node.argument) ? node.argument.literal : undefined); // import("m").T
    else if (ts.isModuleDeclaration(node) && ts.isStringLiteralLikeNode(node.name)) found.add(node.name.text); // declare module "m"
    else if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword || (ts.isIdentifier(node.expression) && node.expression.text === "require"))) {
      throw new Error(`${path}: unsupported module specifier syntax (call to ${node.expression.getText(source)}) at offset ${node.getStart(source)}`);
    }
    node.forEachChild(visit);
  };
  visit(source);
  return found;
};

// Native reference metadata cross-checks the explicit AST scanner. Neither project
// loading nor ambient discovery can add files to the authoritative resolver below.
const references = async (path, source) => {
  const { info, specifiers } = parser.withSource(source, parsed => {
    const specifiers = moduleSpecifiers(path, parsed);
    for (const reference of [...parsed.imports, ...parsed.moduleAugmentations.filter(ts.isStringLiteralLikeNode)]) {
      if (!specifiers.has(reference.text)) throw new Error(`${path}: module specifier ${reference.text} was not found in the syntax tree`);
    }
    return { info: { referencedFiles: parsed.referencedFiles, typeReferenceDirectives: parsed.typeReferenceDirectives }, specifiers };
  });
  const edges = [
    ...[...specifiers].map(specifier => resolveModule(path, specifier)),
    ...info.referencedFiles.map(reference => resolvePath(inRootPath(resolve(dirname(resolve(root, path)), reference.fileName)), path, reference.fileName)),
    ...info.typeReferenceDirectives.map(reference => resolveTypes(path, reference.fileName))
  ];
  return (await Promise.all(edges)).filter(edge => edge !== undefined);
};

const seen = new Set();
const pending = [...entryPoints].sort();
const parser = createDeclarationParser();
try {
  while (pending.length > 0) {
    const path = pending.shift();
    if (seen.has(path)) continue;
    const source = await readFile(resolve(root, path), "utf8");
    seen.add(path);
    pending.push(...await references(path, source));
    pending.sort();
  }
} finally {
  parser.close();
}

const files = await Promise.all([...seen].sort().map(async path => ({
  path,
  sha256: createHash("sha256").update(await readFile(resolve(root, path))).digest("hex")
})));
// Optional fields appear only when non-empty, so a closure without them keeps its schema 2 shape.
const document = {
  schema: 2,
  ...lockIdentity(corpus),
  entryPoints,
  files,
  ...(assets.size > 0 ? { nonDeclarationAssets: [...assets].sort() } : {}),
  ...(external.size > 0 ? { externalModules: [...external].sort() } : {})
};
const rendered = `${JSON.stringify(document, null, 2)}\n`;
if (args.includes("--write")) {
  await writeFile(lockPath, rendered);
  console.log(`wrote ${lockPath} (${files.length} declaration files)`);
} else {
  if (await readFile(lockPath, "utf8") !== rendered) throw new Error("declaration closure drifted; review the lock, curated bindings, runtime evidence, and release notes together");
  console.log(`declaration closure is locked (${files.length} declaration files)`);
}
