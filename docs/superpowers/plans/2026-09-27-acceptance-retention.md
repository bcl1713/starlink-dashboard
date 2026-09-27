<!-- markdownlint-disable MD013 MD022 MD031 MD032 -->
# Acceptance Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build portable, fail-closed acceptance retention that preserves the
protected final authority plus two newer completed candidates per lane.

**Architecture:** A descriptor-confined Python maintenance domain classifies
sealed evidence and marked resources, creates bounded reports, and uses quarantine
plus absence verification only in apply mode. The wrapper preflights before final
allocation and cleans its checkout after Python exits; Compose resources are labelled;
the publish workflow removes only selected build records and inventories GHCR.

**Tech Stack:** Python 3.12 stdlib, pytest, Bash, Docker Compose/Buildx, Git CLI,
GitHub Actions YAML, GitHub REST API via `gh api`.

**Spec:** `docs/superpowers/specs/2026-09-27-acceptance-evidence-retention-design.md`
and `docs/superpowers/specs/2026-09-27-acceptance-retention-operational-lifecycle.md`.
## Global Constraints
- Keep exactly three generations/lane: protected latest final plus two newer complete candidates.
- Report-only is default; deletion needs `--apply`; all paths use canonical no-follow access.
- Ambiguous/corrupt/revoked/live/dirty/unmarked/legacy resources remain and cause an anomaly.
- Never broad-prune Docker/Git; never delete volumes, profiles, user repos, shared caches, or legacy evidence.
- Reports are `0700` JSON under maintenance, record policy SHA/action verification, retain 90 valid reports.
- Final preflight happens before allocation and fails closed; GHCR is report-only, never retagged/deleted.
- Update both acceptance operations runbooks.
## Review Focus
- Manifest or authority symlinks retain data and fail apply mode (Task 2).
- Equal/unparseable protected-final timestamps do not select a winner (Task 2).
- Dirty, attached, or live marked checkouts are never removed (Task 3).
- Unlabelled acceptance-looking Docker resources are inventory-only (Task 4).
- Foreign/paginated/in-progress Actions records or non-`.dockerbuild` artifacts are never deleted (Task 5).
## File Structure
- Create `retention_policy.toml`, `retention.py`, `maintenance.py`,
  `github_retention.py`, `github_retention_cli.py`, and corresponding retention/GitHub tests.
- Modify `compose.py`, wrapper, publish workflow/checker, existing runner/compose/docs tests,
  and both operation runbooks.
### Task 1: Fixed policy and descriptor-confined models

**Files:** Create `tools/acceptance/platform/{retention.py,retention_policy.toml}`
and `tools/tests/test_acceptance_platform_retention.py`; modify `model.py`.

**Interfaces:** `RetentionPolicy.parse(path) -> RetentionPolicy` with `digest`,
`RetentionEntry(path, lane, sha, disposition, reason, byte_size)`,
`canonical_root(path) -> Path`, and `safe_relative(root, candidate) -> PurePosixPath`.
- [ ] **Step 1: Write the failing policy tests.**
```python
def test_policy_is_exact(tmp_path: Path) -> None:
    p = tmp_path / "retention-policy.toml"
    p.write_text("version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n")
    assert RetentionPolicy.parse(p).completed_generations_per_lane == 3

@pytest.mark.parametrize("count", [2, 4, "3"])
def test_policy_rejects_nonfixed_count(tmp_path: Path, count: object) -> None:
    p = tmp_path / "retention-policy.toml"; p.write_text(f"version = 1\ncompleted_generations_per_lane = {count!r}\nmaintenance_report_count = 90\n")
    with pytest.raises(ValueError): RetentionPolicy.parse(p)
```
- [ ] **Step 2: Verify RED.** Run `pytest tools/tests/test_acceptance_platform_retention.py -k policy -v`.
Expected: FAIL, `RetentionPolicy` undefined.
- [ ] **Step 3: Implement exact parser.** Add tracked TOML `(version=1, generations=3,
reports=90)`. Parse with `tomllib`/`evidence.read_nofollow`, SHA-256 raw bytes, reject
unknown/duplicate keys and every other value; add `RetentionDisposition` and entry model.
- [ ] **Step 4: Pin and implement no-follow containment.**
```python
def test_safe_relative_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "state"; root.mkdir(); (root / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError): safe_relative(canonical_root(root), root / "escape" / "x")
```

Walk existing components with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, never `resolve()`.
Run the focused suite; expect PASS.
- [ ] **Step 5: Commit.**
```bash
git add tools/acceptance/platform/{retention.py,retention_policy.toml} tools/acceptance/platform/model.py tools/tests/test_acceptance_platform_retention.py
git commit -m "feat: add fixed acceptance retention policy"
```
### Task 2: Evidence planning, reporting, and safe apply deletion

**Files:** Modify `retention.py` and `test_acceptance_platform_retention.py`.

**Interfaces:** `plan_retention(state_root, policy) -> RetentionPlan` and
`apply_retention(plan, apply: bool) -> RetentionReport`; plan has protected identity,
entries/anomalies; report contains root, policy digest, UTC bounds, dispositions, bytes,
and post-action verification.
- [ ] **Step 1: Write failing sealed-envelope tests.**
```python
def test_keeps_protected_final_and_two_newest(tmp_path: Path) -> None:
    state = build_state_root(tmp_path, final_shas=["a" * 40, "b" * 40, "c" * 40, "d" * 40])
    plan = plan_retention(state, policy)
    assert plan.protected_final.sha == "d" * 40
    assert dispositions_for(plan, Lane.FINAL)["a" * 40] is DELETE

def test_ambiguous_protected_final_is_retained_anomaly(tmp_path: Path) -> None:
    plan = plan_retention(build_ambiguous_protected_final_state(tmp_path), policy)
    assert plan.has_anomalies and all(e.disposition is not DELETE for e in plan.entries)
```

Fixtures use real `write_artifacts`/`seal_fingerprint` and valid runner manifests;
do not mock authority verification.
- [ ] **Step 2: Verify RED.** Run `pytest tools/tests/test_acceptance_platform_retention.py -k 'protected_final or ambiguous' -v`.
Expected: FAIL, planner absent.
- [ ] **Step 3: Implement fail-closed selection.** Open files no-follow, call
`verify_manifest`/`read_fingerprint_authority`, validate runner SHA/ref/final claim/UTC.
Select valid latest protected final, then newest completed to three. Ties, parse/checksum
failure, revocation, conflicting authority, unknown content, or association ambiguity
become retained anomalies. Associate logs/ledgers only by strict SHA paths.
- [ ] **Step 4: Test and implement report/apply behavior.**
```python
def test_report_only_never_removes(tmp_path: Path) -> None:
    state = build_state_with_four_completed_generations(tmp_path)
    assert apply_retention(plan_retention(state, policy), apply=False).bytes_reclaimed == 0
    assert (state / "final" / ("a" * 40)).exists()

def test_apply_quarantines_then_verifies_absence(tmp_path: Path) -> None:
    state = build_state_with_four_completed_generations(tmp_path)
    report = apply_retention(plan_retention(state, policy), apply=True)
    assert not (state / "final" / ("a" * 40)).exists() and report.deletions[0].post_action == "absent"
```

Write `0700` JSON under `maintenance/retention/<UTC>-<UUID>`. Rename eligible data to
root-local UUID quarantine, descriptor-delete there, verify both paths absent. Continue
independent entries but nonzero on anomaly/error; prune only valid reports above 90.
- [ ] **Step 5: Cover lanes and commit.** Add parameterized health/static/diagnostic,
strict logs/ledgers, empty task parent, invalid manifest, unknown nonempty parent,
and symlink refusal tests. Run `pytest tools/tests/test_acceptance_platform_retention.py -v`;
expect PASS; commit `feat: retain bounded sealed acceptance evidence`.
### Task 3: Maintenance CLI, preflight, and checkout lifecycle

**Files:** Create `maintenance.py`; modify wrapper, retention tests, runner tests.

**Interfaces:** `python -m acceptance.platform.maintenance retention --state-root PATH --policy PATH [--apply] [--checkout-root PATH]`; `recover_abandoned_checkouts(root, policy)`;
marker `.acceptance-runner-owner.json` mode `0600` containing lane/SHA/ref/task/creator/time.
- [ ] **Step 1: Write failing CLI/recovery tests.**
```python
def test_cli_defaults_to_report_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = build_state_with_four_completed_generations(tmp_path)
    assert maintenance.main(["retention", "--state-root", str(state), "--policy", str(TRACKED_POLICY)]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "report"

@pytest.mark.parametrize("state", ["dirty", "attached", "active_process", "marker_sha_mismatch"])
def test_unsafe_marked_checkout_is_retained(tmp_path: Path, state: str) -> None:
    checkout = build_marked_checkout(tmp_path, mutation=state)
    assert recover_abandoned_checkouts(checkout.parent, policy).has_anomalies and checkout.exists()
```
- [ ] **Step 2: Verify RED and implement CLI/recovery.** Run matching focused tests;
expect FAIL. Use `argparse` with no force/volume/prune/cache flag. Validate marker,
`git -C` detached exact HEAD/clean porcelain state, and only task-labelled liveness.
Unsafe resources remain and return nonzero.
- [ ] **Step 3: Pin and implement wrapper order.**
```python
def test_final_wrapper_preflights_before_checkout_allocation(tmp_path: Path) -> None:
    events = run_wrapper_with_recorded_commands(tmp_path, lane="final")
    assert events.index("maintenance retention --apply") < events.index("git worktree add")
```

Dispatch `--maintenance retention`; for final, run apply preflight after SHA/ref check,
write marker on detached allocation, run Python without `exec`, then `cd /`, validate
marker/evidence/runtime cleanup, remove exact checkout, verify absence. Cleanup failure
is separate and cannot overwrite sealed evidence.
- [ ] **Step 4: Verify and commit.** Run focused retention/runner lifecycle tests;
expect PASS; commit `feat: add final-lane retention preflight`.
### Task 4: Scoped Docker, workspace, and Git-worktree lifecycle

**Files:** Modify `compose.py`, `maintenance.py`, compose/retention tests.

**Interfaces:** `AcceptanceOwnershipLabels.as_docker_args()` emits owner/lane/SHA/task
labels; `scoped_docker_inventory(...)`; `remove_scoped_docker_resource(...)`.
- [ ] **Step 1: Write failing label/no-prune tests.**
```python
def test_final_resources_have_required_labels() -> None:
    topology = render_task_override(..., candidate_sha="a" * 40, task_id="task-1")
    assert "io.starlink.acceptance.owner=runner" in topology.docker_labels

def test_unlabelled_image_is_inventory_only_without_prune() -> None:
    assert not any("prune" in x for x in recorded_cleanup_commands(unlabelled_image=True))
```
- [ ] **Step 2: Verify RED and implement scoped creation.** Run compose focused suite;
expect FAIL. Thread task/lane/SHA through topology/override/image/Buildx builder labels.
Normal cleanup removes only that builder/cache and confirms absence. Inventory volumes only.
- [ ] **Step 3: Pin exact-ID deletion refusal and implement.**
```python
def test_container_or_protected_ledger_reference_blocks_image_removal() -> None:
    report = retain_docker_resources(FakeDocker(images=[owned_image("a" * 40, referenced=True)]), {"a" * 40}, apply=True)
    assert report.has_anomalies
```

Require all labels, exact inspected ID, eligible SHA, no container/ledger reference.
Remove workspace only with marker/liveness proof; prune only specific registration after
validated checkout absence; never `git worktree prune`.
- [ ] **Step 4: Verify and commit.** Run Docker/workspace/worktree tests; expect PASS;
commit `feat: bound runner-owned acceptance resources`.
### Task 5: Actions build-record selector and GHCR inventory

**Files:** Create `github_retention.py`, `github_retention_cli.py`,
`test_github_retention.py`.

**Interfaces:** `select_expired_dockerbuild_artifacts(runs, artifacts, workflow_path, ref)`
and `inventory_ghcr_versions(versions) -> GhcrInventory` with old SHA/non-SHA/anomalies,
not a delete method.
- [ ] **Step 1: Write failing selector tests.**
```python
def test_selector_keeps_current_plus_two_prior_dev_runs() -> None:
    assert [x.artifact_id for x in select_expired_dockerbuild_artifacts(runs_fixture(), artifacts_fixture(), WORKFLOW, "dev")] == [101, 102]

def test_ghcr_inventory_never_returns_deletion() -> None:
    inventory = inventory_ghcr_versions(package_versions_fixture())
    assert inventory.non_sha_versions == ("latest",) and not hasattr(inventory, "delete")
```
- [ ] **Step 2: Verify RED and implement pure selection/JSON CLI.** Run GitHub tests;
expect FAIL. Consider only exact workflow's completed `dev` runs, retain newest three,
and select only `.dockerbuild` artifacts from expired selected IDs. Pagination, duplicate
IDs, missing dates, foreign runs, or uncertain association raise anomaly. Recognize only
`sha-<40-lowercase-hex>`; report but never mutate GHCR.
- [ ] **Step 3: Add pagination refusal, verify, and commit.**
```python
def test_incomplete_pagination_blocks_partial_deletion() -> None:
    with pytest.raises(GitHubRetentionError, match="pagination"):
        select_expired_dockerbuild_artifacts(runs_fixture(has_next_page=True), {}, WORKFLOW, "dev")
```

Run `pytest tools/tests/test_github_retention.py -v`; expect PASS; commit
`feat: select bounded GitHub build records`.
### Task 6: Publish workflow retention and contract checks

**Files:** Modify `publish-ghcr.yml`, checker, and workflow tests.

**Interfaces:** `retention` job needs successful publish, has `actions: write`, deletes
only selected singular artifact IDs, and emits GHCR inventory.
- [ ] **Step 1: Write failing mutation tests.**
```python
def test_rejects_retention_without_publish_dependency() -> None:
    errors = self.validate_workflow_text(WORKFLOW_PATH.read_text().replace("needs: publish", ""))
    self.assertIn("retention job must depend on successful publish", errors)
```
- [ ] **Step 2: Verify RED and add job.** Run workflow tests; expect FAIL. Restrict to
successful `publish` on `refs/heads/dev`; use `gh api --paginate` plus CLI plan and only
`DELETE repos/${{ github.repository }}/actions/artifacts/$artifact_id`. Upload/log the
plan. Fetch GHCR metadata but no package mutation endpoint. Ambiguity fails retention
visibly without reclassifying image matrix success.
- [ ] **Step 3: Bind checker to named steps; verify and commit.** Require actual
need/condition/permissions/pagination/count 3/ID endpoint and no GHCR deletion; reject
comments/disabled decoys. Run unittest, checker, and YAML parse; expect PASS. Commit
`ci: retain bounded publish build records`.
### Task 7: Runbooks, full verification, and delivery evidence

**Files:** Modify both operation runbooks and `test_acceptance_platform_docs.py`.
- [ ] **Step 1: Write failing docs contract test.**
```python
def test_operations_docs_cover_retention() -> None:
    content = (ROOT / "docs/operations/acceptance-platform.md").read_text()
    assert "--maintenance retention" in content and "never delete GHCR" in content
```
- [ ] **Step 2: Verify RED and document exact operations.** Run docs retention test;
expect FAIL. Document report/apply commands, preflight order, review of protected
candidate/anomalies/`docker ps`/disk, marker recovery, Actions lifecycle, GHCR report-only,
and all deletion prohibitions in both runbooks.
- [ ] **Step 3: Run fresh complete verification.**
```bash
pytest tools/tests/test_acceptance_platform_retention.py tools/tests/test_acceptance_platform_compose.py tools/tests/test_github_retention.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_docs.py -v
python -m unittest tools/tests/test_publish_ghcr_workflow.py -v
python tools/check_publish_ghcr_workflow.py
python -m compileall -q tools/acceptance/platform
./tools/run-acceptance-platform.sh --maintenance retention --state-root "$(mktemp -d)" --policy tools/acceptance/platform/retention_policy.toml
```

Expected: tests/checker/compiler pass; temporary state emits report-only JSON and
removes nothing. Then run canonical static verification with validated policy base,
markdownlint, and link checks.
- [ ] **Step 4: Independently review and deliver.** Fresh reviewer checks root escape,
symlink/authority/report corruption, liveness, Git/Docker scope, and GitHub API overreach.
Fix Critical/Important findings with regressions/re-review. Commit docs, open PR to `dev`
only, and record SHA, verifier/reviewer outputs, and temporary report-only/apply evidence.
## Self-Review
- **Spec coverage:** Tasks 1–2 cover policy/evidence/reports; Task 3 checkout/preflight;
  Task 4 resources/worktrees/volumes; Tasks 5–6 Actions/GHCR; Task 7 operations/verification.
- **Completeness:** Each task names files, interface, RED/GREEN command, safety boundary, and commit.
- **Consistency:** Policy, plan/report, CLI, labels, and GitHub selectors are defined before use.
- **Review focus:** Every high-risk input above has an owning regression test.
