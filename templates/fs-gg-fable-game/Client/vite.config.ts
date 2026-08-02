import { defineConfig } from "vite";

// Development requests to /api and the SignalR hub stay same-origin and are forwarded
// to ASP.NET Core; the hub's WebSocket upgrade needs `ws: true` explicitly.
export default defineConfig({
  server: {
    proxy: {
      "/api": "http://localhost:5000",
      "/hub": { target: "http://localhost:5000", ws: true }
    }
  }
});
