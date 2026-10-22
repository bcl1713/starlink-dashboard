/** Merge only into a separately owned diagnostic Vite config, never production. */
import { fileURLToPath } from "node:url";
export function diagnosticFrontendOptions({ enabled, syntheticRunToken }) {
  if (
    enabled !== true ||
    !/^synthetic-[A-Za-z0-9_-]{1,22}$/.test(syntheticRunToken)
  )
    throw Error("explicit synthetic diagnostic build required");
  return {
    define: { "import.meta.env.VITE_PERF391_DIAGNOSTIC": '"true"' },
    resolve: {
      alias: {
        "@perf391/browser-probe": fileURLToPath(
          new URL("./browser-probe.ts", import.meta.url),
        ),
      },
    },
  };
}
