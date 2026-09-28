from __future__ import annotations

import json
import os
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path, PurePosixPath

import pytest
from acceptance.platform import maintenance, retention, runner
from acceptance.platform.evidence import seal_fingerprint, write_artifacts
from acceptance.platform.model import (
    BrowserProfile,
    Lane,
    PlatformProfile,
    RetentionDisposition,
    RetentionEntry,
)
from acceptance.platform.retention import (
    RetentionLockUnavailable,
    RetentionPolicy,
    apply_retention,
    canonical_root,
    plan_retention,
    safe_relative,
)
from acceptance.platform.runner import RunnerDependencies


def test_policy_is_exact(tmp_path: Path) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(
        "version = 1\n"
        "completed_generations_per_lane = 3\n"
        "maintenance_report_count = 90\n"
    )

    policy = RetentionPolicy.parse(policy_path)

    assert policy.version == 1
    assert policy.completed_generations_per_lane == 3
    assert policy.maintenance_report_count == 90
    assert len(policy.digest) == 64


@pytest.mark.parametrize("count", [2, 4, "3"])
def test_policy_rejects_nonfixed_completed_generation_count(
    tmp_path: Path, count: object
) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(
        "version = 1\n"
        f"completed_generations_per_lane = {count!r}\n"
        "maintenance_report_count = 90\n"
    )

    with pytest.raises(ValueError):
        RetentionPolicy.parse(policy_path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("version", "true"),
        ("version", "1.0"),
        ("completed_generations_per_lane", "true"),
        ("completed_generations_per_lane", "3.0"),
        ("maintenance_report_count", "true"),
        ("maintenance_report_count", "90.0"),
    ],
)
def test_policy_rejects_type_confused_fixed_values(
    tmp_path: Path, key: str, value: str
) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    values = {
        "version": "1",
        "completed_generations_per_lane": "3",
        "maintenance_report_count": "90",
    }
    values[key] = value
    policy_path.write_text(
        "".join(f"{name} = {number}\n" for name, number in values.items())
    )

    with pytest.raises(ValueError):
        RetentionPolicy.parse(policy_path)


@pytest.mark.parametrize(
    "content",
    [
        "version = 2\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n",
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 91\n",
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\nextra = true\n",
        "version = 1\nversion = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n",
    ],
)
def test_policy_rejects_any_value_or_key_outside_fixed_contract(
    tmp_path: Path, content: str
) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(content)

    with pytest.raises(ValueError):
        RetentionPolicy.parse(policy_path)


def test_retention_entry_is_an_immutable_classification_record() -> None:
    entry = RetentionEntry(
        path=PurePosixPath("final") / ("a" * 40),
        lane=Lane.FINAL,
        sha="a" * 40,
        disposition=RetentionDisposition.RETAIN,
        reason="protected final authority",
        byte_size=42,
    )

    assert entry.disposition is RetentionDisposition.RETAIN
    with pytest.raises(FrozenInstanceError):
        setattr(entry, "reason", "mutated")


def test_safe_relative_returns_posix_path_within_descriptor_confined_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    candidate = root / "final" / ("a" * 40)
    candidate.parent.mkdir(parents=True)

    relative = safe_relative(canonical_root(root), candidate)

    assert relative == PurePosixPath("final") / ("a" * 40)


def test_safe_relative_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path)

    with pytest.raises(ValueError):
        safe_relative(canonical_root(root), root / "escape" / "x")


def test_safe_relative_rejects_lexical_escape(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()

    with pytest.raises(ValueError):
        safe_relative(canonical_root(root), root / ".." / "outside")


def test_safe_relative_rejects_retention_root_itself(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()

    with pytest.raises(ValueError):
        safe_relative(canonical_root(root), root)


def test_canonical_root_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root)

    with pytest.raises(ValueError):
        canonical_root(alias)


def test_canonical_root_normalizes_lexical_components_without_resolving(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir()

    assert canonical_root(root / ".." / "state") == root


SHA = "a" * 40
REF = "refs/heads/retention-test"


def _policy(tmp_path: Path) -> RetentionPolicy:
    path = tmp_path / "retention-policy.toml"
    path.write_text(
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n"
    )
    return RetentionPolicy.parse(path)


def _valid_maintenance_report(
    state: Path, policy: RetentionPolicy
) -> dict[str, object]:
    return {
        "root": str(state),
        "policy_digest": policy.digest,
        "tool_version": "acceptance-retention-v1",
        "mode": "report",
        "started_at": "2026-09-27T00:00:00+00:00",
        "ended_at": "2026-09-27T00:00:01+00:00",
        "protected_final": None,
        "entries": [],
        "deletions": [],
        "totals": {"bytes_reclaimed": 0},
        "counts": {
            "entries": 0,
            "deletions": 0,
            "anomalies": 0,
            "pruned_reports": 0,
            "planned_report_prunes": 0,
        },
        "post_run_verification": True,
        "anomalies": [],
    }


def _write_generation(
    state: Path,
    lane: Lane,
    sha: str,
    *,
    ended_at: str,
    final: bool = False,
    outcome: str = "passed",
    ref: str = REF,
    fingerprint_ref: str | None = None,
) -> Path:
    root = state / lane.value / sha
    root.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "sha": sha,
        "ref": ref,
        "lane": lane.value,
        "outcome": outcome,
        "final_acceptance": final,
        "capture": {"started_at": "2026-09-27T00:00:00+00:00", "ended_at": ended_at},
    }
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    write_artifacts(root, {"runner-manifest.json": raw, "artifact.txt": sha.encode()})
    seal_fingerprint(
        root,
        json.dumps(
            {
                "sha": sha,
                "ref": fingerprint_ref if fingerprint_ref is not None else ref,
            },
            sort_keys=True,
        ).encode(),
    )
    return root


def _state_with_generations(tmp_path: Path, lane: Lane = Lane.FINAL) -> Path:
    state = tmp_path / "state"
    for index, letter in enumerate("abcd", start=1):
        _write_generation(
            state,
            lane,
            letter * 40,
            ended_at=f"2026-09-27T00:00:0{index}+00:00",
            final=lane is Lane.FINAL,
        )
    return state


def _entry(plan: object, lane: Lane, sha: str) -> RetentionEntry:
    return next(
        entry for entry in plan.entries if entry.lane is lane and entry.sha == sha
    )


def _runner_profile() -> PlatformProfile:
    return PlatformProfile(
        "platform-v1",
        "b" * 64,
        BrowserProfile(
            Path("/tmp/browser"), Path("/tmp/browser/chrome"), "1", 1, "d" * 64
        ),
    )


def test_retention_recognizes_and_protects_runner_published_candidate(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    result = runner.run(
        [
            "--lane",
            "final",
            "--sha",
            SHA,
            "--ref",
            REF,
            "--profile",
            str(tmp_path / "profile.toml"),
            "--contract",
            str(
                Path(__file__).resolve().parents[2]
                / "tools/acceptance/contracts/v2-mission-retirement.toml"
            ),
            "--fingerprint",
            "current",
            "--evidence-root",
            str(state),
            "--task-root",
            str(tmp_path / "task"),
            "--acceptance-task",
            "retention-fixture",
        ],
        dependencies=RunnerDependencies(
            load_profile=lambda _: _runner_profile(),
            validate_health=lambda *_: object(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: None,
        ),
    )

    assert result.exit_code == 0
    plan = plan_retention(state, _policy(tmp_path))
    try:
        assert not plan.has_anomalies
        assert plan.protected_final is not None
        assert plan.protected_final.path == PurePosixPath(f"candidates/{SHA}")
        assert plan.protected_final.disposition is RetentionDisposition.RETAIN
    finally:
        apply_retention(plan, apply=False)


def test_retention_accepts_sealed_failed_final_as_non_authoritative_history(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    _write_generation(
        state,
        Lane.FINAL,
        SHA,
        ended_at="2026-09-27T00:00:01+00:00",
        outcome="failed",
    )

    plan = plan_retention(state, _policy(tmp_path))
    try:
        assert not plan.has_anomalies
        assert plan.protected_final is None
        assert _entry(plan, Lane.FINAL, SHA).disposition is RetentionDisposition.RETAIN
    finally:
        apply_retention(plan, apply=False)


def test_maintenance_invalid_arguments_emit_json_error_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert maintenance.main(["retention", "--unknown"]) == 2

    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"]
    assert captured.err == ""


def test_cli_defaults_to_report_only_and_closes_its_plan_lease(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _state_with_generations(tmp_path)
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n"
    )

    assert (
        maintenance.main(
            ["retention", "--state-root", str(state), "--policy", str(policy_path)]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "report"
    follow_up = plan_retention(state, RetentionPolicy.parse(policy_path))
    follow_up.close()


def test_cli_returns_nonzero_when_checkout_recovery_refuses_an_unsafe_checkout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _state_with_generations(tmp_path)
    checkout_root = tmp_path / "checkouts"
    checkout_root.mkdir()
    checkout = _marked_checkout(checkout_root, mutation="dirty")
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n"
    )

    assert (
        maintenance.main(
            [
                "retention",
                "--state-root",
                str(state),
                "--policy",
                str(policy_path),
                "--checkout-root",
                str(checkout.parent),
            ]
        )
        == 1
    )

    assert checkout.exists()
    assert "checkout_anomalies" in json.loads(capsys.readouterr().out)


def _marked_checkout(root: Path, *, mutation: str) -> Path:
    checkout = root / "checkout"
    checkout.mkdir()
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "acceptance@example.invalid"],
        ["git", "config", "user.name", "Acceptance"],
    ):
        subprocess.run(command, cwd=checkout, check=True)
    (checkout / "tracked.txt").write_text("tracked\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=checkout, check=True)
    subprocess.run(["git", "checkout", "--detach", "-q"], cwd=checkout, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    marker = {
        "lane": "final",
        "sha": sha,
        "ref": "refs/heads/feat/acceptance",
        "task": "task-123",
        "creator": "acceptance-runner-v1",
        "time": "2026-09-27T00:00:00+00:00",
    }
    if mutation == "dirty":
        (checkout / "tracked.txt").write_text("dirty\n")
    elif mutation == "attached":
        subprocess.run(["git", "switch", "-qc", "attached"], cwd=checkout, check=True)
    elif mutation == "marker_sha_mismatch":
        marker["sha"] = "b" * 40
    (checkout / ".acceptance-runner-owner.json").write_text(json.dumps(marker))
    (checkout / ".acceptance-runner-owner.json").chmod(0o600)
    return checkout


@pytest.mark.parametrize(
    "state", ["dirty", "attached", "active_process", "marker_sha_mismatch"]
)
def test_unsafe_marked_checkout_is_retained_as_an_anomaly(
    tmp_path: Path, state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = _marked_checkout(tmp_path, mutation=state)
    if state == "active_process":
        monkeypatch.setattr(maintenance, "_task_is_live", lambda _task: True)

    report = maintenance.recover_abandoned_checkouts(checkout.parent, _policy(tmp_path))

    assert report.has_anomalies
    assert checkout.exists()


def test_safe_marked_checkout_is_removed_after_validation(tmp_path: Path) -> None:
    checkout_root = tmp_path / "checkouts"
    checkout_root.mkdir()
    checkout = _marked_checkout(checkout_root, mutation="safe")
    policy_root = tmp_path / "policy"
    policy_root.mkdir()

    report = maintenance.recover_abandoned_checkouts(
        checkout_root, _policy(policy_root)
    )

    assert not report.has_anomalies
    assert report.removed == (checkout,)
    assert not checkout.exists()


def test_unmarked_immediate_checkout_child_is_retained_as_an_anomaly(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "unmarked-checkout"
    checkout.mkdir()

    report = maintenance.recover_abandoned_checkouts(tmp_path, _policy(tmp_path))

    assert report.has_anomalies
    assert checkout.exists()
    assert any(
        "unmarked-checkout" in anomaly and "ownership marker" in anomaly
        for anomaly in report.anomalies
    )


@pytest.mark.parametrize(
    ("failure_mode", "expected_anomaly"),
    [
        ("absent", "ownership marker is missing"),
        ("malformed", "ownership marker fields are invalid"),
        ("mismatched", "checkout HEAD does not match marker SHA"),
    ],
)
def test_recovery_retains_real_detached_checkout_after_marker_creation_failure(
    tmp_path: Path, failure_mode: str, expected_anomaly: str
) -> None:
    checkout_root = tmp_path / "checkouts"
    checkout_root.mkdir()
    checkout = _marked_checkout(checkout_root, mutation="safe")
    marker = checkout / ".acceptance-runner-owner.json"
    failing_chmod = tmp_path / "chmod"
    failing_chmod.write_text(
        "#!/usr/bin/env bash\n"
        'case "$MARKER_FAILURE_MODE" in\n'
        '  absent) rm -- "$2" ;;\n'
        "  malformed) printf '{}' > \"$2\" ;;\n"
        '  mismatched) printf \'%s\\n\' "$MISMATCHED_MARKER" > "$2" ;;\n'
        "esac\n"
        "exit 1\n"
    )
    failing_chmod.chmod(0o755)
    mismatched = json.loads(marker.read_text())
    mismatched["sha"] = "b" * 40
    creation = subprocess.run(
        [
            "bash",
            "-c",
            'umask 077; printf \'{}\' > "$1"; "$2" 0600 "$1"',
            "_",
            str(marker),
            str(failing_chmod),
        ],
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "MARKER_FAILURE_MODE": failure_mode,
            "MISMATCHED_MARKER": json.dumps(mismatched),
        },
    )

    assert creation.returncode == 1
    report = maintenance.recover_abandoned_checkouts(checkout_root, _policy(tmp_path))

    assert checkout.exists()
    assert report.has_anomalies
    assert any(expected_anomaly in anomaly for anomaly in report.anomalies)


def test_keeps_protected_final_and_two_newest(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.protected_final.sha == "d" * 40
    assert _entry(plan, Lane.FINAL, "a" * 40).disposition is RetentionDisposition.DELETE
    assert _entry(plan, Lane.FINAL, "b" * 40).disposition is RetentionDisposition.RETAIN


def test_ambiguous_protected_final_is_retained_anomaly(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    _write_generation(
        state, Lane.FINAL, "e" * 40, ended_at="2026-09-27T00:00:04+00:00", final=True
    )

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_conflicting_fingerprint_and_runner_refs_are_an_anomaly(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    _write_generation(
        state,
        Lane.FINAL,
        "e" * 40,
        ended_at="2026-09-27T00:00:05+00:00",
        final=True,
        fingerprint_ref="refs/heads/conflicting-authority",
    )

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert any("fingerprint ref mismatch" in anomaly for anomaly in plan.anomalies)
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_nonfinal_lane_rejects_final_acceptance_claim(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path, Lane.HEALTH)
    _write_generation(
        state,
        Lane.HEALTH,
        "e" * 40,
        ended_at="2026-09-27T00:00:05+00:00",
        final=True,
    )

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert any("only final lane" in anomaly for anomaly in plan.anomalies)
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_unknown_maintenance_content_blocks_deletion(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    maintenance = state / "maintenance"
    maintenance.mkdir()
    (maintenance / "unrecognized.json").write_text("do not ignore")

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert any("unknown maintenance content" in anomaly for anomaly in plan.anomalies)
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_truncated_maintenance_report_blocks_deletion(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    reports = state / "maintenance" / "retention"
    reports.mkdir(parents=True)
    (reports / "invented.json").write_text(
        json.dumps({"root": str(state), "policy_digest": _policy(tmp_path).digest})
    )

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert any(
        "invalid maintenance retention report" in anomaly for anomaly in plan.anomalies
    )
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"mode": "report"}),
        lambda payload: payload.update({"deletions": []}),
        lambda payload: payload["entries"].append(payload["protected_final"]),
        lambda payload: payload["entries"].__setitem__(
            0, {**payload["entries"][0], "reason": "wrong protected reason"}
        ),
    ],
    ids=(
        "report-only-claims-deletion",
        "deletion-record-does-not-match-entry",
        "protected-final-is-duplicated",
        "protected-final-reason-disagrees",
    ),
)
def test_semantically_impossible_maintenance_reports_block_deletion(
    tmp_path: Path, mutation: object
) -> None:
    state = _state_with_generations(tmp_path)
    policy = _policy(tmp_path)
    protected_sha = "d" * 40
    deleted_sha = "a" * 40
    payload = _valid_maintenance_report(state, policy)
    payload.update(
        {
            "mode": "apply",
            "protected_final": {
                "path": f"final/{protected_sha}",
                "lane": "final",
                "sha": protected_sha,
                "reason": "protected final authority",
            },
            "entries": [
                {
                    "path": f"final/{protected_sha}",
                    "lane": "final",
                    "sha": protected_sha,
                    "disposition": "retain",
                    "reason": "protected final authority",
                    "bytes": 7,
                },
                {
                    "path": f"final/{deleted_sha}",
                    "lane": "final",
                    "sha": deleted_sha,
                    "disposition": "delete",
                    "reason": "expired completed generation",
                    "bytes": 5,
                },
            ],
            "deletions": [
                {
                    "path": f"final/{deleted_sha}",
                    "sha": deleted_sha,
                    "post_action": "absent",
                }
            ],
            "totals": {"bytes_reclaimed": 5},
            "counts": {
                "entries": 2,
                "deletions": 1,
                "anomalies": 0,
                "pruned_reports": 0,
                "planned_report_prunes": 0,
            },
            "post_run_verification": True,
            "anomalies": [],
        }
    )
    assert callable(mutation)
    mutation(payload)
    reports = state / "maintenance" / "retention"
    reports.mkdir(parents=True)
    (reports / "impossible.json").write_text(json.dumps(payload))

    plan = plan_retention(state, policy)

    assert plan.has_anomalies
    assert any(
        "invalid maintenance retention report" in anomaly for anomaly in plan.anomalies
    )
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_leftover_quarantine_content_blocks_future_deletion(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    stranded = state / ".retention-quarantine" / "stranded"
    stranded.mkdir(parents=True)
    (stranded / "evidence.txt").write_text("never ignore")

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert any("retained quarantine content" in anomaly for anomaly in plan.anomalies)
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_report_only_never_removes(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    report = apply_retention(plan_retention(state, _policy(tmp_path)), apply=False)

    assert report.bytes_reclaimed == 0
    assert (state / "final" / ("a" * 40)).exists()
    assert report.deletions == ()


def test_planning_holds_a_private_regular_mode_0600_lock_until_report_seals(
    tmp_path: Path,
) -> None:
    state = _state_with_generations(tmp_path)
    plan = plan_retention(state, _policy(tmp_path))
    lock = state / ".retention.lock"

    identity = os.lstat(lock)

    assert not os.path.islink(lock)
    assert (identity.st_mode & 0o170000) == 0o100000
    assert (identity.st_mode & 0o777) == 0o600
    assert (state / "final" / ("a" * 40)).exists()
    apply_retention(plan, apply=False)


def test_second_runner_cannot_plan_while_first_runner_lease_is_held(
    tmp_path: Path,
) -> None:
    state = _state_with_generations(tmp_path)
    first = plan_retention(state, _policy(tmp_path))

    with pytest.raises(RetentionLockUnavailable):
        plan_retention(state, _policy(tmp_path))

    assert (state / "final" / ("a" * 40)).exists()
    apply_retention(first, apply=False)


def test_complete_apply_removes_generation_while_its_planning_lease_is_held(
    tmp_path: Path,
) -> None:
    state = _state_with_generations(tmp_path)
    plan = plan_retention(state, _policy(tmp_path))

    report = apply_retention(plan, apply=True)

    assert not (state / "final" / ("a" * 40)).exists()
    assert report.anomalies == ()
    follow_up = plan_retention(state, _policy(tmp_path))
    apply_retention(follow_up, apply=False)


def test_lease_releases_after_anomalous_report_seals(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    (state / "mystery").mkdir()
    (state / "mystery" / "keep.txt").write_text("retained")
    plan = plan_retention(state, _policy(tmp_path))

    report = apply_retention(plan, apply=True)

    assert report.anomalies
    follow_up = plan_retention(state, _policy(tmp_path))
    apply_retention(follow_up, apply=False)


def test_apply_deletes_planned_generation_with_atomic_exchange(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    report = apply_retention(plan_retention(state, _policy(tmp_path)), apply=True)

    assert not (state / "final" / ("a" * 40)).exists()
    assert len(report.deletions) == 1
    assert report.deletions[0].sha == "a" * 40
    assert report.deletions[0].post_action == "absent"
    assert report.bytes_reclaimed > 0
    assert report.pruned_reports == 0
    assert report.anomalies == ()
    assert (report.path.stat().st_mode & 0o777) == 0o700


def test_exchange_identity_mismatch_rolls_replacement_back_to_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state_with_generations(tmp_path)
    plan = plan_retention(state, _policy(tmp_path))
    source = state / "final" / ("a" * 40)
    displaced = state / "displaced-generation"

    def replace_quarantined_entry(quarantined: Path, _entry: RetentionEntry) -> None:
        os.rename(quarantined, displaced)
        quarantined.mkdir()
        (quarantined / "must-survive.txt").write_text("replacement")

    monkeypatch.setattr(retention, "_after_exchange", replace_quarantined_entry)

    report = apply_retention(plan, apply=True)

    assert (source / "must-survive.txt").read_text() == "replacement"
    assert displaced.exists()
    assert report.deletions == ()
    assert any("identity mismatch" in anomaly for anomaly in report.anomalies)


def test_apply_without_atomic_exchange_capability_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _state_with_generations(tmp_path)
    plan = plan_retention(state, _policy(tmp_path))
    source = state / "final" / ("a" * 40)

    def unavailable(*_args: object) -> None:
        raise retention._AtomicExchangeUnavailable("unsupported")

    monkeypatch.setattr(retention, "_renameat2_exchange", unavailable)

    report = apply_retention(plan, apply=True)

    assert source.exists()
    assert report.deletions == ()
    assert report.bytes_reclaimed == 0
    assert any("atomic exchange unavailable" in anomaly for anomaly in report.anomalies)


@pytest.mark.parametrize("lane", [Lane.HEALTH, Lane.STATIC, Lane.DIAGNOSTIC])
def test_retains_newest_three_completed_generations_per_nonfinal_lane(
    tmp_path: Path, lane: Lane
) -> None:
    state = _state_with_generations(tmp_path, lane)

    plan = plan_retention(state, _policy(tmp_path))

    assert _entry(plan, lane, "a" * 40).disposition is RetentionDisposition.DELETE
    assert all(
        _entry(plan, lane, letter * 40).disposition is RetentionDisposition.RETAIN
        for letter in "bcd"
    )


def test_invalid_manifest_unknown_nonempty_parent_and_empty_task_parent_are_anomalies(
    tmp_path: Path,
) -> None:
    state = _state_with_generations(tmp_path)
    (state / "final" / ("a" * 40) / "artifact.txt").write_text("tampered")
    (state / "mystery").mkdir()
    (state / "mystery" / "unknown").write_text("keep")
    (state / "tasks").mkdir()

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert (
        _entry(plan, Lane.FINAL, "a" * 40).disposition is RetentionDisposition.ANOMALY
    )
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_strict_sha_log_and_ledger_association_blocks_delete(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    (state / "logs" / "final").mkdir(parents=True)
    (state / "logs" / "final" / ("a" * 39 + "b")).write_text("unassociated")
    (state / "ledgers").mkdir()
    (state / "ledgers" / "not-a-sha.json").write_text("unassociated")

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_exact_sha_logs_ledgers_and_task_parents_are_associated(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    sha = "a" * 40
    (state / "logs" / "final" / sha).mkdir(parents=True)
    (state / "logs" / "final" / sha / "run.log").write_text("associated")
    (state / "ledgers" / sha).mkdir(parents=True)
    (state / "ledgers" / sha / "ledger.json").write_text("associated")
    (state / "tasks" / sha).mkdir(parents=True)

    plan = plan_retention(state, _policy(tmp_path))

    assert not plan.has_anomalies
    assert _entry(plan, Lane.FINAL, sha).disposition is RetentionDisposition.DELETE


def test_symlinked_generation_is_refused_without_removal(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    target = state / "final" / ("a" * 40)
    alias = state / "final" / ("e" * 40)
    alias.symlink_to(target, target_is_directory=True)

    plan = plan_retention(state, _policy(tmp_path))

    assert plan.has_anomalies
    assert alias.is_symlink()
    assert all(
        entry.disposition is not RetentionDisposition.DELETE for entry in plan.entries
    )


def test_prunes_only_valid_maintenance_reports_above_ninety(tmp_path: Path) -> None:
    state = _state_with_generations(tmp_path)
    reports = state / "maintenance" / "retention"
    reports.mkdir(parents=True)
    policy = _policy(tmp_path)
    for index in range(91):
        path = reports / f"2026-09-27T00-00-{index:02d}-report.json"
        path.write_text(json.dumps(_valid_maintenance_report(state, policy)))
        path.chmod(0o700)
    (reports / "corrupt.json").write_text("not json")

    report = apply_retention(plan_retention(state, _policy(tmp_path)), apply=False)

    assert report.pruned_reports == 0
    assert report.planned_report_prunes == 2
    assert len(list(reports.glob("*.json"))) == 93
    assert (reports / "corrupt.json").exists()


def test_apply_prunes_only_planned_valid_reports_and_accounts_for_them(
    tmp_path: Path,
) -> None:
    state = _state_with_generations(tmp_path)
    reports = state / "maintenance" / "retention"
    reports.mkdir(parents=True)
    policy = _policy(tmp_path)
    for index in range(91):
        path = reports / f"2026-09-27T00-00-{index:02d}-report.json"
        path.write_text(json.dumps(_valid_maintenance_report(state, policy)))
        path.chmod(0o700)
    report = apply_retention(plan_retention(state, policy), apply=True)

    assert report.planned_report_prunes == 2
    assert report.pruned_reports == 2
    assert len(list(reports.glob("*.json"))) == 90
    assert report.anomalies == ()
