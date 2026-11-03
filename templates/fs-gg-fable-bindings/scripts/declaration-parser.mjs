import { API } from "typescript/unstable/sync";
import * as ast from "typescript/unstable/ast";

export { ast };

// The native project parses exactly one caller-supplied declaration. It never owns
// dependency resolution: all other filesystem reads fail closed, including ambient types.
export function createDeclarationParser() {
  const cwd = "/fsgg-declaration-parser";
  const config = `${cwd}/tsconfig.json`;
  const file = `${cwd}/input.d.ts`;
  const files = new Map([[config, JSON.stringify({
    compilerOptions: { noEmit: true, noResolve: true, noLib: true, types: [] },
    files: ["input.d.ts"]
  })]]);
  let opened = false;
  let closed = false;
  const api = new API({
    cwd,
    fs: {
      readFile: path => files.get(path) ?? null,
      fileExists: path => files.has(path),
      directoryExists: path => path === cwd,
      getAccessibleEntries: path => ({ files: path === cwd ? ["tsconfig.json", "input.d.ts"] : [], directories: [] }),
      realpath: path => path
    }
  });
  return {
    withSource(text, consume) {
      if (closed) throw new Error("declaration parser is closed");
      files.set(file, text);
      // A virtual-file change notification alone can retain the prior native AST.
      // Invalidate both native and client caches before reusing the one-file project.
      api.clearSourceFileCache();
      const snapshot = api.updateSnapshot(opened
        ? { fileChanges: { invalidateAll: true } }
        : { openProjects: [config] });
      opened = true;
      try {
        const project = snapshot.getProject(config);
        const names = project?.program.getSourceFileNames();
        if (names?.length !== 1 || names[0] !== file) throw new Error("native declaration parser expanded its isolated project");
        const source = project.program.getSourceFile(file);
        if (!source || source.text !== text) throw new Error("native declaration parser returned stale or missing source");
        return consume(source);
      } finally {
        snapshot.dispose();
      }
    },
    close() {
      if (!closed) {
        closed = true;
        api.close();
      }
    }
  };
}
