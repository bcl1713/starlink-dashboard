import { defineConfig } from "vitest/config";
import path from "node:path";
const root = process.env.PERF391_FRONTEND_ROOT;
export default defineConfig({
  cacheDir: path.resolve(import.meta.dirname, "../../artifacts/vitest-focused"),
  root: path.resolve(import.meta.dirname, "../.."),
  resolve: {
    alias: {
      "@perf391/browser-probe": path.resolve(
        import.meta.dirname,
        "../../browser-probe.ts",
      ),
      "@app": root ? path.join(root, "src") : "",
      "@": root ? path.join(root, "src") : "",
    },
  },
  define: { "import.meta.env.VITE_PERF391_DIAGNOSTIC": '"true"' },
  test: {
    setupFiles: [path.resolve(import.meta.dirname, "setup.ts")],
    include: ["tests/frontend/*.test.{ts,tsx}"],
    maxWorkers: 1,
    fileParallelism: false,
  },
});
