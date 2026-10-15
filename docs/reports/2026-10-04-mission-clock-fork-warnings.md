# Mission clock lookup fork warning investigation

**Date:** 2026-10-04

**Status:** COMPLETE

**Issue:** [225](https://github.com/bcl1713/starlink-dashboard/issues/225)

Mission activation's offline city lookup caused the multithreaded fork warnings
reported in mission-route tests. Selecting the geocoder's supported
single-process mode removes that process creation while preserving geographic
results. No warning filter, mission behavior, or concurrency assertion changed.

## Reproduction and cause

The inspected baseline was `dev` commit
`f71a7034955bbbd8805d3310ae92af4e86581383`. Fresh environments resolved the
tracked requirements with uv 0.12.19 and CPython 3.11.16 and 3.13.15. The
backend Dockerfile and tracked interpreter selection use Python 3.11; Python
3.13 was also selected explicitly to reproduce the reported warnings.

Running the existing mission-route and offline-geography tests produced:

| Interpreter | Passed | Fork warnings | Other warnings |
| ----------- | ------ | ------------- | -------------- |
| 3.11.16     | 26     | 0             | 1              |
| 3.13.15     | 26     | 140           | 1              |

Python 3.11's lack of this diagnostic does not establish safe process creation.
A separate real lookup on Python 3.13 with a background thread active emitted 20
fork warnings. The warning count depends on the available CPU count. This
investigation reproduced warnings, not a deadlock.

The call chain is:

```text
activate_leg
  -> OfflineClockGeography.locality_at
  -> reverse_geocoder.search (default mode=2)
  -> cKDTree_MP.pquery
  -> multiprocessing.Process.start
  -> os.fork
```

Installed reverse-geocoder 1.5.1 starts one worker per available CPU for each
query in mode 2, even for a single coordinate. Mission activation performs
lookups while TestClient's application thread is alive. The separate lifecycle
isolation test already uses spawn; it was not this warning's source.

## Change and regression coverage

`OfflineClockGeography.locality_at` now passes `mode=1`. This selects the
ordinary SciPy KDTree and retains the same packaged city data and output
normalization. The dependency documents this
[single-process mode](https://github.com/thampiman/reverse-geocoder#usage).
Repository inspection found no other reverse-geocoder consumer that could
initialize its singleton in another mode first.

The new regression runs real packaged-data lookups in a fresh interpreter, with
another thread active. It intercepts child-process startup and fails before an
unsafe child can run. It verifies Omaha, Washington DC, Tokyo, and a repeat
lookup through a second geography instance. Interpreter isolation keeps the
dependency's singleton from concealing an unsafe first initialization.

Before the change, the regression failed with
`locality lookup started a child process`. Afterward it passed. Existing mission
activation, import/export, and lifecycle concurrency tests remain intact.

## Verification and dependency provenance

Both complete backend suites passed with **1,422 passed, 20 skipped, and two
unrelated warnings**: SlowAPI's deprecated HTTP 413 name and Cartopy's facecolor
warning. Python 3.13 verification promoted the reported multithreaded fork
diagnostic to an error. Its focused mission-route/geography run passed 27 tests
with only the SlowAPI warning.

Run from repository root:

```sh
UV_CACHE_DIR=/tmp/starlink-225-uv-cache ./tools/verify backend
UV_CACHE_DIR=/tmp/starlink-225-uv-cache UV_PYTHON=3.13 \
  PYTEST_ADDOPTS='-W error:.*multi-threaded.*:DeprecationWarning' \
  ./tools/verify backend
```

The fresh environments used reverse-geocoder 1.5.1, timezonefinder 9.0.0, pytest
9.1.1, pytest-asyncio 1.4.0, FastAPI 0.142.2, Starlette 1.7.0, and AnyIO 4.15.1.
Python 3.11 resolved NumPy 2.4.6 and SciPy 1.17.1; Python 3.13 resolved NumPy
2.5.3 and SciPy 1.18.1. Full installed version inventories are retained:

- [Python 3.11 dependencies](evidence/2026-10-04-mission-clock-fork-warnings/python311-dependencies.txt)
- [Python 3.13 dependencies](evidence/2026-10-04-mission-clock-fork-warnings/python313-dependencies.txt)

Black and Ruff passed across all backend application and test files. The
repository static gate passed in the declared development environment, including
frontend lint/format checks, documentation links, and policy tests. Independent
review found no correctness or test reliability issues. Local baseline,
regression, and full-suite logs are `/tmp/issue-225-baseline-py311.log`,
`/tmp/issue-225-baseline-py313.log`, `/tmp/issue-225-regression-red.log`,
`/tmp/issue-225-regression-green.log`, `/tmp/issue-225-full-py311.log`, and
`/tmp/issue-225-full-py313.log`.
