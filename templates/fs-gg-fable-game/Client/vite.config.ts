import { defineConfig } from "vite";

// Development requests to /api and the SignalR hub stay same-origin and are forwarded
// to ASP.NET Core; the hub's WebSocket upgrade needs `ws: true` explicitly.
//
// Two pages are built. `index.html` is the game client. `renderers.html` runs the
// FS.GG.Game.Render conformance kit on the game's renderers (Renderers.fs) in a browser; it is
// the only page that imports the canvas renderer surfaces and their npm packages, so the game page does not
// carry them. Browser.Tests/renderer-conformance.spec.ts serves it with `vite preview`.
export default defineConfig({
  build: {
    rollupOptions: {
      input: { main: "index.html", renderers: "renderers.html" }
    }
  },
  server: {
    proxy: {
      "/api": "http://localhost:5000",
      "/hub": { target: "http://localhost:5000", ws: true }
    }
  }
});
