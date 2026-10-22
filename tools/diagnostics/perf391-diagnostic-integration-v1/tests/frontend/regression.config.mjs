import { defineConfig, mergeConfig } from "vitest/config";
import { loadConfigFromFile } from "vite";
import path from "node:path";
const root = process.env.PERF391_FRONTEND_ROOT;
const { config: base } = await loadConfigFromFile(
  { command: "serve", mode: "test" },
  path.join(root, "vite.config.ts"),
);
export default mergeConfig(
  base,
  defineConfig({
    root,
    cacheDir: path.resolve(
      import.meta.dirname,
      "../../artifacts/vitest-regression",
    ),
    resolve: {
      alias: {
        "@perf391/browser-probe": path.resolve(
          import.meta.dirname,
          "../../browser-probe.ts",
        ),
      },
    },
    define: {
      "import.meta.env.VITE_PERF391_DIAGNOSTIC":
        process.env.PERF391_DIAGNOSTIC_TEST_MODE === "off"
          ? '"false"'
          : '"true"',
    },
    test: {
      setupFiles: [path.resolve(import.meta.dirname, "setup.ts")],
      maxWorkers: 2,
      fileParallelism: true,
    },
  }),
);
