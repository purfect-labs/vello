import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // In dev, proxy /api calls to the FastAPI backend — no CORS config needed
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
