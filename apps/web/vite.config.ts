import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { catalogStubPlugin } from "./stub/plugin";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const useStub = env.VITE_USE_STUB === "true" || mode === "stub";
  return {
    plugins: [react(), catalogStubPlugin(useStub)],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: useStub
        ? undefined
        : {
            "/api": {
              target: "http://localhost:8000",
              changeOrigin: true,
            },
          },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      css: true,
    },
  };
});
