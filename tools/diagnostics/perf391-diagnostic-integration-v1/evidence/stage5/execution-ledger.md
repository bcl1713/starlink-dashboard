# Stage 5 execution ledger

Starting commit: 9f50189ed4ad067e49135b2325bae754f3539d23. Authorization: PR
#408 checkpoint 6353772496 and this session.

- Isolated feature branch descends from origin/dev through the explicit
  requested starting commit; primary checkout remains dev.
- Existing reviewed Stage 1-4 design governs qualification; no new production
  design or runtime permission needed.
- Independent review rechecked all ten Stage 4 findings. Two residual Important
  defects reproduced and repaired within integration.py/verify_evidence.py;
  production/patch/frozen files unchanged.
- New replay-runner termination gap reproduced by the independent review; signal
  cancellation/finally cleanup fixed and regression passed. Extra-source
  preflight rejection added after a failing test.
- Ruling: missing module hashes keep CLI v1 chart projection unavailable. The
  positive API path uses reviewed projection hashes independently matched to
  fresh guarded exports. Cost: CLI complete sidecar evidence alone cannot
  qualify actual chart content.
- Ruling: synthetic fake-Page/probe fixtures normalize host identity and clock
  fields explicitly. They qualify adapter integration only; no
  image/browser/paint/wire/performance claims follow.
- Failure ledger: uncached Ruff 0.17.2 unavailable under offline install; used
  cached 0.17.1. Initial sandbox qualification worker teardown hit outer 60s
  timeout; host tree subsequently absent. Focused initial discovery import
  ordering failed; fixed test imports. Initial replay nested asyncio.run failed;
  fixed runner to offload synchronous replay. Initial frontend regression ran
  wrong cwd/diagnostic mode and was stopped after identified failures; 2,102
  tests subsequently passed with intended settings. Raw app TypeScript config
  lacks diagnostic alias; private opt-in config passes. Root solution TypeScript
  check contains no sources and is not used as proof. Early coverage export ran
  before its test child finished and returned no data; final coverage is
  exported after exit. Broad Ruff findings are separately inventoried as
  existing debt, not silently accepted as clean.
- Ruling: no services, Docker resources, listeners, real browsers or application
  network traffic created. Test children are bounded and recorded by scoped
  owners; private exports, dependency links and environment are removed after
  evidence capture. Keep open-PR worktree and committed evidence.
- Stop after publishing Stage 5 to draft #408. No runtime qualification
  authorized. Stage 3B deferred; 1.5-second observer-cadence rule unchanged.
