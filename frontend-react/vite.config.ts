import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development, /api/* is proxied to the FastAPI backend so the
// browser never needs CORS. Override the target with BACKEND_URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.BACKEND_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
