import { defineConfig } from "vite";

// Development requests to /api stay same-origin and are forwarded to ASP.NET Core.
export default defineConfig({ server: { proxy: { "/api": "http://localhost:5000" } } });
