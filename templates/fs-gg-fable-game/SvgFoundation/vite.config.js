import { resolve } from "node:path";

export default {
  root: resolve(import.meta.dirname),
  resolve: {
    alias: {
      "@microsoft/signalr": resolve(import.meta.dirname, "../Client/node_modules/@microsoft/signalr/dist/esm/index.js")
    }
  },
  build: { outDir: "dist", emptyOutDir: true },
};
