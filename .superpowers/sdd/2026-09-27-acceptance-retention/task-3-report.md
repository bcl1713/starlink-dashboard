# Task 3 report — maintenance CLI, preflight, and checkout lifecycle

## Delivered

- Added `acceptance.platform.maintenance` with the required `retention` command:
  - `--state-root` and `--policy` are required.
  - Report-only is the default; `--apply` is the only mutation switch.
  - The parser exposes no force, volume, prune, cache, or scheduler controls.
  - The command emits the sealed retention report JSON to stdout.
  - Retention anomalies and checkout-recovery anomalies return exit status `1`.
  - The API always calls `apply_retention`, including report-only mode, so a retained planning lease is closed after report sealing.

- Added cooperative abandoned-checkout recovery:
  - Checks only immediate children of an explicit canonical checkout root.
  - Requires a regular, no-follow ownership marker with exact `0600` permissions and the exact six fields: `lane`, `sha`, `ref`, `task`, `creator`, and `time`.
  - Validates the marker lane, SHA/ref, creator version prefix, and timezone-bearing timestamp.
  - Refuses and reports marked checkouts that are dirty, attached, have an SHA mismatch, or have a live process carrying the exact `--acceptance-task=<task>` label.
  - Removes only a fully validated detached checkout at the marker SHA with clean porcelain status (excluding its ownership marker). Independent repositories use confined recursive removal after validation; Git linked worktrees use their common Git directory’s `worktree remove` command.

- Added final-lane wrapper lifecycle:
  - `--maintenance retention ...` dispatches directly to the maintenance module.
  - Final invocations require explicit state root, policy, checkout root, and task identity.
  - Verifies the requested ref resolves to the requested SHA before preflight.
  - Runs `maintenance retention --apply` before `git worktree add`.
  - Allocates an exact detached worktree, writes a mode-`0600` ownership marker, and invokes Python without `exec`.
  - Captures the runner exit code, changes to `/`, validates the marker/checkout, then removes the exact worktree and verifies it disappeared.
  - A runner failure still performs cleanup and preserves its original nonzero status when cleanup succeeds. A cleanup failure retains the checkout, returns nonzero, and does not modify sealed runner evidence.

## TDD evidence

Observed RED before the corresponding implementations:

1. CLI report-only test initially failed collection because `acceptance.platform.maintenance` did not exist.
2. Unsafe checkout recovery cases initially failed because `recover_abandoned_checkouts` and task liveness checking did not exist.
3. Wrapper order test initially failed because maintenance preflight was absent.
4. Marker-lifecycle regression failed after temporarily removing marker creation: wrapper retained the checkout with marker validation failure.
5. Runner-failure cleanup regression failed after temporarily removing the `set +e`/status capture: the shell exited before `worktree remove`.
6. Safe recovery regression failed against the initial linked-worktree-only removal approach; recovery now handles validated independent repositories safely.

## Verification

Passed:

```text
PYTHONPATH=tools pytest tools/tests/test_acceptance_platform_retention.py tools/tests/test_acceptance_platform_runner.py -q
122 passed in 13.80s
```

Also passed syntax and diff checks:

```text
bash -n tools/run-acceptance-platform.sh
python3 -m py_compile tools/acceptance/platform/maintenance.py
git diff --check
```

The full `tools/tests` run completed with `1362 passed, 1 skipped, 3 failed`. The three failures are outside Task 3 and were not modified:

- `test_grafana_synchronously_installs_pinned_infinity_datasource`: expected Grafana plugin installation string is absent from the existing compose file.
- Two `tools/tests/test_verify.py` tests: existing candidate typing-policy gate rejects the absent `ACCEPTANCE_POLICY_BASE_SHA` environment variable before their mocked dispatch.

## Scope

Modified only Task 3 implementation and its retention/runner tests. No Docker scoped lifecycle, GitHub workflow, plan, or ledger files were changed.

## Review-finding rework evidence

- Wrapper recovery identity is now preserved as an exact process argv element:
  `--acceptance-task=<task>`. The final-lane wrapper starts the runner through a
  small `exec -a` shell boundary so the runner process retains that label while
  Python receives its normal supported arguments.
- Recovery inventories every immediate checkout-root child. A missing ownership
  marker is an anomaly that blocks cleanup rather than an ignored directory.
- Marker creation is now an explicit checked step after allocation. A failure
  returns nonzero, leaves the checkout in place, and leaves an observable
  marker/recovery anomaly for the next maintenance pass.
- Added a real wrapper-launch regression that starts a live runner process,
  calls the production `/proc` liveness scan without monkeypatching, and proves
  recovery retains the active checkout. Added unmarked-child and
  marker-creation-failure regressions.

### RED → GREEN

The new focused regressions were first run against the pre-rework implementation:

```text
3 failed
```

They demonstrated respectively that an unmarked immediate child was silently
ignored, the live wrapper process had no exact recovery label, and marker
creation failure exited without reporting the retained checkout. After the
minimal wrapper and recovery changes, all three passed.

### Final verification

```text
PYTHONPATH=tools pytest tools/tests/test_acceptance_platform_retention.py tools/tests/test_acceptance_platform_runner.py -q
125 passed in 8.87s

bash -n tools/run-acceptance-platform.sh
python3 -m py_compile tools/acceptance/platform/maintenance.py
git diff --check
```

The requested historical `121 passed, 1 failed` result did not reproduce in
this checkout. The repository's declared focused invocation, `PYTHONPATH=tools`,
is a valid environment prerequisite and produced a clean baseline (`122 passed`)
before this rework; the three added regressions account for the final total of
`125 passed`. No runner product code was changed to suppress a diagnostic.

## Round 2 re-review correction

The prior marker-creation-failure test was not sufficient evidence: its fake
`chmod` failed after the `umask 077` write had already created a valid mode-0600
marker, and its subsequent recovery anomaly could arise from the fake checkout's
non-Git layout. That claim is superseded.

The corrected wrapper regression now creates a real independent Git repository,
commits it, checks out detached HEAD, then simulates marker creation failure by
removing the marker from the fake `chmod` before returning nonzero. It asserts:

- the production wrapper returns `1` and retains the checkout;
- production `recover_abandoned_checkouts` retains that real detached checkout;
- recovery reports the missing ownership-marker anomaly specifically.

A companion recovery regression covers all three malformed ownership outcomes
(absent, malformed, and SHA-mismatched markers) on real detached checkouts.

### Round 2 RED → GREEN evidence

With the production missing-marker anomaly append temporarily removed, the
corrected wrapper regression failed as intended:

```text
1 failed: CheckoutRecoveryReport(removed=(), anomalies=()).has_anomalies
```

Restoring the production fail-closed anomaly handling produced:

```text
PYTHONPATH=tools pytest \
  tools/tests/test_acceptance_platform_retention.py::test_recovery_retains_real_detached_checkout_after_marker_creation_failure \
  tools/tests/test_acceptance_platform_runner.py::test_final_wrapper_retains_checkout_when_marker_creation_fails -q
4 passed in 0.41s

bash -n tools/run-acceptance-platform.sh
python3 -m py_compile tools/acceptance/platform/maintenance.py
git diff --check
```
