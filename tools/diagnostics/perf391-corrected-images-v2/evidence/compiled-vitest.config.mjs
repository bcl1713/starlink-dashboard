export default {
  "root": "/home/oracle-worker/Work/starlink-dashboard/.worktrees/perf391-corrected-forge/tools/diagnostics/perf391-diagnostic-integration-v1",
  "cacheDir": "/tmp/perf391-corrected-forge/vitest-cache",
  "resolve": {
    "alias": {
      "../../browser-probe": "/tmp/perf391-corrected-forge/compiled-probe.mjs"
    }
  },
  "test": {
    "setupFiles": [
      "/home/oracle-worker/Work/starlink-dashboard/.worktrees/perf391-corrected-forge/tools/diagnostics/perf391-diagnostic-integration-v1/tests/frontend/setup.ts"
    ],
    "include": [
      "tests/frontend/probe.test.ts"
    ],
    "maxWorkers": 1,
    "fileParallelism": false
  }
};
