import { execSync } from "node:child_process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build-time version identifier shown in the UI header so it is always clear
// which build is running. In the Docker/CI build the commit SHA is passed via
// the VITE_APP_VERSION env var (git is not available inside the image); for a
// local build we fall back to the current git short hash.
function resolveAppVersion(): string {
  const fromEnv = process.env.VITE_APP_VERSION;
  if (fromEnv && fromEnv.trim()) {
    return fromEnv.trim().slice(0, 7);
  }
  try {
    return execSync("git rev-parse --short HEAD").toString().trim();
  } catch {
    return "dev";
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(resolveAppVersion())
  },
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  preview: {
    port: 4173,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  }
});
