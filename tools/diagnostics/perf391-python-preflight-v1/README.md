# Private Python preflight correction — offline checkpoint

Starting commit: `de434540998587f105b720d1477133c8deb57b4a` (descends from
`origin/dev`); isolated branch `diag/perf391-python-preflight`.
Authority: [latest orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6363230112).

**PASS_OFFLINE_PREFLIGHT_NO_RUNTIME_STARTED. A executions: 0; C executions: 0.
Stop for review. Runtime retry remains NO-GO.**

The private CPython 3.11.16 venv fixes the operator verifier's incompatible system
package selection. No system dist-packages, global packages, dependency-path
injection or host Python changes were used. Existing project-module lookup in the
historical preflight wrapper is retained; it does not supply Python dependencies.
The pinned inventory comes from the existing diagnostic integration
`requirements-test.txt`; resolution adds typing-extensions 4.16.0. Only the six
schema dependencies are installed, with binary wheels and required hashes.
`resolution.lock` retains the resolver's full artifact hashes;
`requirements.lock` restricts installation to the exact verified wheels below.

## Exact installed wheels

| Package | Version | SHA-256 |
| --- | --- | --- |
| attrs | 26.1.0 | `c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309` |
| jsonschema | 4.19.2 | `eee9e502c788e89cb166d4d37f43084e3b64ab405c795c03d343a4dbc2c810fc` |
| jsonschema-specifications | 2025.9.1 | `98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe` |
| referencing | 0.37.0 | `381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231` |
| rpds-py | 2026.9.1 | `136a1c3fe4402b7008bc81cb62ee538481795b61a7e83df88dff3b3f02b726ff` |
| typing_extensions | 4.16.0 | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` |

[evidence/wheels.json](evidence/wheels.json) records wheel filenames and URLs.
Each downloaded wheel matched both its lock hash and PyPI digest; installed
payload bytes matched the wheel. A second fresh venv installed these wheels with
`uv pip sync --offline --no-index --find-links … --require-hashes --only-binary :all:`
and passed the same functional checks. Network was used only for dependency
acquisition and GitHub publication; preflight performed no network fetches.
Initial sandbox DNS refusal was resolved through approved host execution.

## Verification

- [Environment evidence](evidence/environment.json): CPython 3.11.16; all six
  packages loaded from the private venv. Draft202012Validator validates a valid
  integer and rejects an invalid string via a referencing Registry/$ref.
  HashTrieMap persistent insertion operates correctly.
- [Dependency check](evidence/dependency-check.log): `uv pip check` reports all six
  installed packages compatible. [Offline recreation](evidence/offline-recreation.log)
  and [second environment evidence](evidence/offline-environment.json) pass.
- Native `rpds/rpds.cpython-311-x86_64-linux-gnu.so`: ELF64 x86-64, CPython 3.11 ABI;
  SHA-256 `be6a965c619fc93dd16b4094ee63a73ad24e9a1e1915e5120679ea574ea7b7c6`.
  `file`, `readelf -h`, and `ldd` pass; libgcc_s, libpthread, libc and the loader
  resolve without missing dependencies. Exact paths and interpreter hash retained.
- [Preflight result](evidence/preflight.json) and [log](evidence/preflight.log):
  both immutable receipt/schema closures, all four retained image IDs/labels,
  stage-5 source identities (621 release files / 97 source files), collector and
  frozen identities pass. Active readiness, Node and logging correction manifests
  pass. The historical compiler regenerates the original build plan byte-for-byte;
  only the previously approved logging override hashes differ in corrected plans.
  Both effective Compose configurations match the approved configurations.
- Rootless actor Docker inspection used the inherited daemon/context. Compose was
  used only for `config`; no build, pull, create, up or run was issued.

The retained preflight is administratively adapted only for task/evidence paths,
starting commit and authority; it ends after the existing Compose checks. It
retains the original checkpoint's HEAD guard, so its recorded invocation is bound
to the starting commit. No Node extraction/execution, Playwright/Chromium startup,
frontend readiness HTTP, A/C launcher/executor, capture, calibration, benchmark or
sustained test ran. No redundant test was added. Runtime-only qualifications,
including the historical frontend refusal and 1.5-second observer cadence, remain
unresolved/unexercised and require separate authorization.

## Reproduction and cleanup

Create a task-owned venv with the recorded Python 3.11.16 interpreter; unset
PYTHONPATH, set PYTHONNOUSERSITE=1, and use `uv pip sync --python <venv>/bin/python
--require-hashes --only-binary :all: requirements.lock`. Acquire the exact wheels
from the recorded URLs for offline `--no-index --find-links <wheel-dir>` use.
Run `verify-environment.py`, `uv pip check --python <venv>/bin/python`, then the
existing preflight wrapper under `timeout --kill-after=10s 5m` at the bound
starting commit with these checkpoint files available. The environment verifier
and wheel verifier are evidence utilities, not additions to a test suite.

[Host cleanup](evidence/cleanup.json) confirms no task process survivors,
containers, networks, disposable volumes or A/C port listeners. Both private venvs,
wheel downloads, resolver cache and generated source contexts were removed with
the task scratch `/tmp/perf391-python-preflight`. The review worktree and evidence
remain. No runtime resources were started. Immutable receipts/images/source
references, frozen harness, collector and historical failed evidence are unchanged.
[GitHub state](evidence/github-state.json) confirms #403/#405–#408 draft/open/unmerged,
#390/#391 open; #404 is an open issue, not a PR. The 1.5-second threshold is unchanged.
