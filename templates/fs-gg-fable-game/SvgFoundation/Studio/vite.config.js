import { resolve } from "node:path";

export default {
  root: resolve(import.meta.dirname),
  build: { outDir: "dist", emptyOutDir: true },
};
