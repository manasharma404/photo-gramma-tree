import { defineConfig } from "vite";

// Dev: `npm run dev` proxies API calls to the FastAPI app on :8000.
// Build: `npm run build` -> web/dist, which api/main.py serves at "/". Everything is bundled: no CDN at runtime.
const api = "http://127.0.0.1:8000";
export default defineConfig({
  base: "/",
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 2000 },
  server: {
    proxy: {
      "/advisor": api, "/measure": api, "/accuracy": api, "/tiles": api, "/health": api, "/field": api,
      "/field-static": api,
    },
  },
});
