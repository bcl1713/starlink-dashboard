# Task 6 report — Publish workflow retention and contract checks

## Delivered

- Added a separate `retention` job that runs only after a successful `publish` on `dev`.
- Scoped the retention job to `contents: read`, `packages: read`, and `actions: write`.
- Paginated workflow runs and each run's artifacts, normalized workflow paths for the Task 5 selector, supplied the explicit current run ID, logged/uploaded the JSON deletion plan, and deleted only artifact IDs selected by that plan.
- Added report-only paginated GHCR version inventories; no package mutation endpoint is used.
- Extended the contract checker to bind retention assertions to enabled named steps and reject missing/disabled/mutated retention behavior.

## Fix round 1

- Added job-scoped `GH_TOKEN: ${{ github.token }}` so every retention `gh api` command receives GitHub Actions authentication.
- Hardened disabled-step detection to strip inline comments and evaluate literal false conditions, negation, literal comparisons, and literal boolean conjunction/disjunction.
- Added mutation regressions for disabled deletion, GHCR inventory, and artifact-upload steps, plus missing retention-token coverage.

## Verification

- `python -m unittest tools.tests.test_publish_ghcr_workflow -v` — 20 tests passed.
- `python tools/check_publish_ghcr_workflow.py` — passed.
- PyYAML parse of `.github/workflows/publish-ghcr.yml` — passed.
- `git diff --check` — passed.

## Commit

- `c8787026 ci: retain bounded publish build records`
- `c72376f1 fix(ci): harden retention workflow checks`

## Fix round 2: short-circuit disabled-step detection

- Corrected literal boolean evaluation to apply short-circuit dominance even when the other operand is dynamic: `false && dynamic` evaluates false, and `true || dynamic` evaluates true.
- Added mutation regressions proving the checker rejects a deletion step disabled by `false && github.ref == 'refs/heads/dev'` and an upload step disabled by `!(true || github.ref == 'refs/heads/dev')`.
- Added balanced outer-parenthesis handling so the negated disjunction is evaluated before the surrounding negation.

## Fix round 2 verification

- RED against base `93350a71`: both new conditions were misclassified as enabled (`[False, False]`).
- Focused mutation suite — 2 tests passed.
- `python -m unittest tools/tests/test_publish_ghcr_workflow.py -v` — 22 tests passed.
- `python tools/check_publish_ghcr_workflow.py` — passed.
- PyYAML parse of `.github/workflows/publish-ghcr.yml` — passed.
- `python -m compileall -q tools/check_publish_ghcr_workflow.py tools/tests/test_publish_ghcr_workflow.py` — passed.
- `git diff --check` — passed.
