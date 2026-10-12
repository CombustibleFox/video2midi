import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the FastAPI backend (uvicorn app.main:app) runs on :8000.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/jobs": "http://localhost:8000" } },
});
