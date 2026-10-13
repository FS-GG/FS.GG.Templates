import { resolve } from "node:path";

const wasmPolicy = process.env.FsGgWasmPolicyExample === "true";
const wasmBase = process.env.FSGG_WASM_POLICY_BASE ?? "/wasm-example/";
if (wasmPolicy && (!/^\/(?:[A-Za-z0-9_-]+\/)+$/.test(wasmBase) || wasmBase === "/")) {
  throw new Error("WASM policy requires an explicit non-root deployment base");
}
export default {
  base: wasmPolicy ? wasmBase : "/",
  root: resolve(import.meta.dirname),
  resolve: {
    alias: {
      ...(wasmPolicy ? { "@fsgg-wasm": resolve(import.meta.dirname, "obj/wasm-policy-public/_content/FS.GG.Wasm.Browser") } : {}),
      "@microsoft/signalr": resolve(import.meta.dirname, "../Client/node_modules/@microsoft/signalr/dist/esm/index.js")
    }
  },
  // The default keeps Vite's implicit public directory, including owner assets.
  ...(wasmPolicy ? { publicDir: resolve(import.meta.dirname, "obj/wasm-policy-public") } : {}),
  build: { outDir: "dist", emptyOutDir: true },
};
