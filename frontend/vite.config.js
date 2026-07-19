import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local dev: `npm run dev` serves the SPA on :5173 and proxies API calls to
// the FastAPI backend on :8080 (`uvicorn app.main:app --port 8080` in backend/).
// In the container the built bundle is served by FastAPI itself — no proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/healthz": "http://localhost:8080",
    },
  },
});
