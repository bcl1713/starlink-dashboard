/** Build overlay only; installed next to the exported original vite.config.ts. */
import { mergeConfig } from "vite";
import base from "./vite.config.ts";
import { diagnosticFrontendOptions } from "/diagnostic/frontend-config.mjs";

export default mergeConfig(base, {
  ...diagnosticFrontendOptions({
    enabled: true,
    syntheticRunToken: "synthetic-build391",
  }),
  resolve: {
    alias: { "@perf391/browser-probe": "/diagnostic/browser-runtime.ts" },
  },
  build: { manifest: true, sourcemap: false },
  plugins: [
    {
      name: "perf391-compiled-module-closure",
      generateBundle(_options, bundle) {
        const modules = {};
        for (const [file, chunk] of Object.entries(bundle)) {
          if (chunk.type !== "chunk") continue;
          modules[file] = Object.entries(chunk.modules)
            .map(([id, value]) => ({
              id: id
                .replaceAll(
                  "/workspace/frontend/mission-planner/",
                  "frontend/mission-planner/",
                )
                .replaceAll("/diagnostic/", "diagnostic/"),
              renderedLength: value.renderedLength,
              renderedExports: value.renderedExports,
            }))
            .sort((a, b) => a.id.localeCompare(b.id));
        }
        const live = Object.values(modules)
          .flat()
          .filter((m) => m.renderedLength > 0);
        for (const suffix of [
          "diagnostic/browser-runtime.ts",
          "diagnostic/browser-probe.ts",
          "src/services/overview-history.ts",
          "src/hooks/api/useOverviewHistory.ts",
          "src/pages/OverviewMetricHistoryPanel.tsx",
        ]) {
          if (!live.some((m) => m.id.endsWith(suffix)))
            throw Error("diagnostic compiled module absent: " + suffix);
        }
        this.emitFile({
          type: "asset",
          fileName: "perf391-module-closure.json",
          source:
            JSON.stringify({
              schema: "perf391-compiled-modules-v1",
              modules,
              graph: Array.from(this.getModuleIds())
                .sort()
                .map((id) => {
                  const m = this.getModuleInfo(id);
                  const normalize = (x) =>
                    x
                      .replaceAll(
                        "/workspace/frontend/mission-planner/",
                        "frontend/mission-planner/",
                      )
                      .replaceAll("/diagnostic/", "diagnostic/");
                  return {
                    id: normalize(id),
                    isEntry: m.isEntry,
                    isExternal: m.isExternal,
                    imports: m.importedIds.map(normalize),
                    dynamicImports: m.dynamicallyImportedIds.map(normalize),
                  };
                }),
            }) + "\n",
        });
      },
    },
  ],
});
