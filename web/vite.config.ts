import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During dev, proxy the API + WebSocket to the SAMS backend on :8787.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
