import assert from "node:assert/strict";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const { createDeclarationParser, ast } = await import(pathToFileURL(resolve(process.argv[2])));
const parser = createDeclarationParser();
try {
  parser.withSource(`/// <reference path="./unloaded.d.ts" />
/// <reference types="unloaded-types" />
export * as NS from "unloaded-module";
/** import("not-an-edge") */
declare module "augmentation" { interface A {} }
declare global { interface GlobalFixture {} }
`, source => {
    assert.deepEqual(source.imports.map(node => node.text), ["unloaded-module"]);
    assert.deepEqual(source.moduleAugmentations.filter(ast.isStringLiteralLikeNode).map(node => node.text), ["augmentation"]);
    assert.deepEqual(source.referencedFiles.map(reference => reference.fileName), ["./unloaded.d.ts"]);
    assert.deepEqual(source.typeReferenceDirectives.map(reference => reference.fileName), ["unloaded-types"]);
    assert.ok(ast.isStringLiteralLikeNode(source.imports[0]));
  });
  assert.equal(parser.withSource('export type B = import("new-input").B;', source => source.imports[0].text), "new-input");
  assert.throws(() => parser.withSource("export interface C {}", () => { throw new Error("consumer refusal"); }), /consumer refusal/);
  assert.equal(parser.withSource("export interface D {}", source => source.text), "export interface D {}");
} finally {
  parser.close();
}
parser.close();
assert.throws(() => parser.withSource("", () => {}), /parser is closed/);
console.log("PASS native parser isolation, references, fresh snapshots and refusal cleanup");
