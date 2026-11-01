import { defineConfig } from "vite";

// Development requests to /api and the SignalR hub stay same-origin and are forwarded
// to ASP.NET Core; the hub's WebSocket upgrade needs `ws: true` explicitly.
//
// Two pages are built. `index.html` is the game client, which can draw the arena with the three renderers
// of Renderers.fs (Stage.fs). `renderers.html` runs the FS.GG.Game.Render conformance kit on the same
// renderers in a browser. Browser.Tests serves both with `vite preview`.
// FSGG_AUTHORITY selects the authority server the page's requests go to (Browser.Tests serves the built client with
// `vite preview` next to its own authority server and sets it); `vite` and `vite preview` default to ASP.NET Core's 5000.
const authority = process.env.FSGG_AUTHORITY ?? "http://localhost:5000";

export default defineConfig({
  build: {
    rollupOptions: {
      input: { main: "index.html", renderers: "renderers.html" }
    }
  },
  server: {
    proxy: {
      "/api": authority,
      "/hub": { target: authority, ws: true }
    }
  }
});
