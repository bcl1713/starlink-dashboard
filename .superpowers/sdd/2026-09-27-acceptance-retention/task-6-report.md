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
