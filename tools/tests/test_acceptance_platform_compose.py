from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from acceptance.platform.compose import (
    BoundedComposeDiagnostics,
    BuildLedger,
    BuildProgressMonitor,
    BuildSupervisionFailure,
    CommandResult,
    SubprocessComposeExecutor,
    TaskTopology,
    build_final,
    cleanup_compose,
    reconcile_build,
    render_task_override,
    require_override_path,
    resolve_topology,
    start_no_build,
)
from acceptance.platform.model import (
    BrowserProfile,
    BuildLedgerKey,
    PlatformProfile,
    ProductContract,
    RuntimeControl,
    StaticGroup,
)

SHA = "a" * 40
PROFILE = PlatformProfile(
    "platform-v1",
    "b" * 64,
    BrowserProfile(Path("browser"), Path("browser/chrome"), "1", 1, "d" * 64),
)
CONTRACT = ProductContract(
    name="mission-retirement",
    services=("starlink-location", "mission-planner"),
    static_groups=(StaticGroup("unit", Path("."), ("pytest",)),),
    controls=(RuntimeControl("health", "/health", 200),),
    journey_adapter=Path("tools/acceptance/journey.py"),
    assets=(Path("fixtures/example.json"),),
    checksum="c" * 64,
)
KEY = BuildLedgerKey(SHA, "b" * 64, "c" * 64)


def configured_executor(
    *, run: Callable[[tuple[str, ...], float | None], CommandResult]
) -> SubprocessComposeExecutor:
    return SubprocessComposeExecutor(retain=lambda _: None, execute=run)


def test_typed_fixture_configures_executor_without_method_reassignment() -> None:
    executor = configured_executor(run=lambda _argv, _timeout: CommandResult(0, "typed"))

    assert executor.run(("docker", "compose")) == CommandResult(0, "typed")
    assert "run" not in executor.__dict__


def test_require_override_path_rejects_missing_optional_path() -> None:
    with pytest.raises(ValueError, match="rendered override path is required"):
        require_override_path(None)


def test_task_topology_rejects_missing_override_at_compose_boundary(tmp_path: Path) -> None:
    topology = TaskTopology(
        tmp_path,
        "acceptance-typed",
        SHA,
        CONTRACT.services,
        tmp_path / "compose.env",
        None,
        tmp_path / "compose.root-public-env.yml",
        tmp_path / "topology.validated.json",
        {"starlink-location": 18000, "mission-planner": 15173},
    )

    with pytest.raises(ValueError, match="rendered override path is required"):
        _ = topology.argv


def test_typed_topology_tests_do_not_dereference_optional_override_path() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    direct_dereferences = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "override_path"
        and isinstance(node.value, ast.Name)
    ]

    assert direct_dereferences == []


def _complete_two_image_log(project: str = "acceptance-abc") -> str:
    return f"""#10 exporting to image
#10 naming to docker.io/library/{project}-starlink-location:latest
#10 unpacking to docker.io/library/{project}-starlink-location:latest
#10 DONE 0.1s
#20 exporting to image
#20 naming to docker.io/library/{project}-mission-planner:latest
#20 unpacking to docker.io/library/{project}-mission-planner:latest
#20 DONE 0.1s"""


@dataclass
class FakeClock:
    now: float = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_progress_parser_ignores_repeated_spinner_and_unchanged_byte_frames() -> None:
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)

    assert monitor.observe("#31 [builder] RUN npm run build\n") is not None
    clock.advance(599)
    assert monitor.observe("#31 [builder] RUN npm run build\n") is None
    assert monitor.observe("#24 transferring context: 53.65MB 25.2s\n") is not None
    clock.advance(1)
    assert monitor.observe("#24 transferring context: 53.65MB 25.2s\n") is None


def test_progress_parser_accepts_only_qualifying_buildkit_progress() -> None:
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)

    assert monitor.observe("#1 [internal] load build definition\n").kind == "stage"
    assert monitor.observe("#1 DONE 0.0s\n").kind == "done"
    assert monitor.observe("#2 transferring context: 1.0MB 1.0s\n").kind == "bytes"
    assert monitor.observe("#2 transferring context: 1025kB 2.0s\n").kind == "bytes"
    assert monitor.observe("#3 [builder] RUN npm run build\n").kind == "stage"
    assert monitor.observe("#3 emitted application bundle\n").kind == "run_output"
    assert monitor.observe("#3 WARNING incidental output\n") is None
    assert monitor.observe("#3 emitted application bundle\n") is None


@pytest.mark.parametrize(
    "frame",
    (
        "#3 599.0s RUN npm run build\n",
        "#3 600.0s / running npm run build\n",
        "#3 [platform retained Compose output truncated]\n",
    ),
)
def test_progress_parser_does_not_count_changing_run_status_or_truncation(
    frame: str,
) -> None:
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)

    assert monitor.observe("#3 [builder] RUN npm run build\n") is not None
    clock.advance(599)
    assert monitor.observe(frame) is None
    clock.advance(1)

    with pytest.raises(BuildSupervisionFailure, match="build_stalled"):
        monitor.check()


def test_progress_parser_does_not_count_elapsed_buildkit_run_status_frames() -> None:
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)

    assert monitor.observe("#3 [builder] RUN npm run build\n") is not None
    for frame in (
        "#3 100.0s [builder 5/7] RUN npm run build\n",
        "#3 200.5s [builder 6/7] RUN npm run build\n",
        "#3 300.0s [builder 6/7] RUN npm run build -- --mode production\n",
        "#3 600.0s [builder 6/7] RUN npm run build\n",
    ):
        clock.advance(100)
        assert monitor.observe(frame) is None
    clock.advance(200)

    with pytest.raises(BuildSupervisionFailure, match="build_stalled"):
        monitor.check()


def test_progress_parser_counts_bracketed_active_run_command_output() -> None:
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)

    assert monitor.observe("#3 [builder] RUN npm run build\n") is not None
    clock.advance(599)

    event = monitor.observe("#3 [webpack] running production compilation\n")

    assert event is not None
    assert event.kind == "run_output"
    assert event.detail == "#3 [webpack] running production compilation"
    clock.advance(1)
    monitor.check()


def test_progress_monitor_prioritizes_outer_deadline_over_stall_at_exact_limit() -> (
    None
):
    clock = FakeClock()
    monitor = BuildProgressMonitor(clock.monotonic)
    monitor.observe("#1 [internal] load build definition\n")
    for _ in range(17):
        clock.advance(100)
        monitor.observe(f"#{_ + 2} [builder] RUN step {_}\n")
    clock.advance(100)

    with pytest.raises(BuildSupervisionFailure, match="build_deadline_exceeded"):
        monitor.check()


def test_build_stall_closes_candidate_ledger_and_blocks_startup(
    tmp_path: Path,
) -> None:
    candidate_sha = "b" * 40
    topology = _topology(tmp_path, candidate_sha=candidate_sha)
    executor = _executor(config=_resolved_config(topology))
    ledger = BuildLedger(tmp_path / "ledger")
    clock = FakeClock()
    resolve_topology(topology, CONTRACT, executor)
    rendered = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
    assert {
        name: service["build"]["args"]
        for name, service in rendered["services"].items()
    } == {
        "starlink-location": {"ACCEPTANCE_CANDIDATE_SHA": candidate_sha},
        "mission-planner": {"ACCEPTANCE_CANDIDATE_SHA": candidate_sha},
    }
    original_run = executor._run_default

    def run_stalled_build(
        argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if "build" in argv:
            assert "--pull" in argv
            assert "--no-cache" not in argv
            monitor = BuildProgressMonitor(clock.monotonic)
            monitor.observe("#31 [builder] RUN npm run build\n")
            clock.advance(600)
            try:
                monitor.check("#31 [builder] RUN npm run build\n")
            except BuildSupervisionFailure as error:
                raise BuildSupervisionFailure(
                    error.kind,
                    error.last_event,
                    error.output,
                    started_at="2026-09-25T12:00:00+00:00",
                    ended_at="2026-09-25T12:10:02+00:00",
                    elapsed_seconds=602.0,
                ) from error
        return original_run(argv, timeout_seconds=timeout_seconds)

    executor.run_override = lambda argv, timeout_seconds: run_stalled_build(
        argv, timeout_seconds=timeout_seconds
    )

    candidate_key = BuildLedgerKey(
        candidate_sha, KEY.profile_checksum, KEY.contract_checksum
    )
    with pytest.raises(BuildSupervisionFailure, match="build_stalled"):
        build_final(topology, PROFILE, CONTRACT, candidate_key, ledger, executor)

    record = ledger.read(candidate_key)
    assert record["state"] == "closed"
    assert record["reason"].startswith("build_stalled:")
    assert record["supervision"] == {
        "kind": "build_stalled",
        "started_at": "2026-09-25T12:00:00+00:00",
        "ended_at": "2026-09-25T12:10:02+00:00",
        "elapsed_seconds": 602.0,
        "last_event": {
            "kind": "stage",
            "elapsed_seconds": 0.0,
            "detail": "#31 [builder] RUN npm run build",
        },
    }
    with pytest.raises(ValueError, match="usable"):
        start_no_build(topology, CONTRACT, candidate_key, ledger, executor)


def test_subprocess_executor_streams_combined_output_and_preserves_exit() -> None:
    retained: list[str] = []
    result = SubprocessComposeExecutor(retained.append).run(
        (
            sys.executable,
            "-c",
            "import sys; print('plain-buildkit'); sys.exit(124)",
            "build",
            "--progress=plain",
        )
    )

    assert result.returncode == 124
    assert result.output == "plain-buildkit\n"
    assert retained == ["plain-buildkit\n"]


def test_subprocess_executor_kills_surviving_group_descendant_and_drains_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from acceptance.platform import compose

    monkeypatch.setattr(compose, "_FINAL_BUILD_STALL_SECONDS", 0.15)
    monkeypatch.setattr(compose, "_FINAL_BUILD_TERMINATE_GRACE_SECONDS", 0.05)
    retained: list[str] = []
    child_ready = "child-ready\n"
    script = """
import signal
import subprocess
import sys
import time

child = subprocess.Popen([
    sys.executable, "-c",
    "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('child-ready', flush=True); time.sleep(30)",
])
print(f"leader={os.getpid()} child={child.pid}", flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
time.sleep(30)
"""
    script = "import os\n" + script

    started = time.monotonic()
    with pytest.raises(BuildSupervisionFailure, match="build_stalled") as failure:
        SubprocessComposeExecutor(retained.append).run(
            (sys.executable, "-c", script, "build", "--progress=plain")
        )
    assert time.monotonic() - started < 2
    assert retained.count(child_ready) == 1
    assert child_ready in failure.value.output
    child_pid = int(
        next(line.split("child=")[1] for line in retained if "child=" in line)
    )
    child_state = Path(f"/proc/{child_pid}/status")
    deadline = time.monotonic() + 1
    while True:
        try:
            status = child_state.read_text()
        except OSError:
            break
        if "State:\tZ" in status:
            break
        assert time.monotonic() < deadline
        time.sleep(0.01)


def test_terminate_process_group_reaps_leader_after_process_lookup_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from acceptance.platform import compose

    process = subprocess.Popen((sys.executable, "-c", "import time; time.sleep(0.05)"))
    monkeypatch.setattr(
        compose.os, "killpg", lambda *_: (_ for _ in ()).throw(ProcessLookupError)
    )

    compose._terminate_process_group(process)

    assert process.returncode == 0


def test_bounded_compose_diagnostics_redacts_credentials_and_marks_truncation() -> None:
    diagnostics = BoundedComposeDiagnostics(max_bytes=96)
    diagnostics.retain("#1 token=top-secret-password\n")
    diagnostics.retain("#2 " + "x" * 100)

    retained = diagnostics.output.decode()
    assert "top-secret-password" not in retained
    assert "token=<redacted>" in retained
    assert "[platform retained Compose output truncated]" in retained
    assert len(diagnostics.output) <= 96


@pytest.mark.parametrize(
    "line",
    (
        "Authorization: Bearer top-secret-password\n",
        "authorization=Basic abcdef\n",
    ),
)
def test_bounded_compose_diagnostics_redacts_complete_authorization_values(
    line: str,
) -> None:
    diagnostics = BoundedComposeDiagnostics()

    diagnostics.retain(line)

    retained = diagnostics.output.decode()
    assert "top-secret-password" not in retained
    assert "abcdef" not in retained
    assert "Bearer" not in retained
    assert "Basic" not in retained
    assert "<redacted>" in retained


@pytest.mark.parametrize("max_bytes", (0, 1, 16, 44))
def test_bounded_compose_diagnostics_never_exceeds_tiny_cap_when_truncated(
    max_bytes: int,
) -> None:
    diagnostics = BoundedComposeDiagnostics(max_bytes=max_bytes)

    diagnostics.retain("x" * (max_bytes + 1))

    assert len(diagnostics.output) <= max_bytes


def test_duplicate_build_ledger_claim_is_refused(tmp_path: Path) -> None:
    ledger = BuildLedger(tmp_path)
    ledger.claim(KEY)
    with pytest.raises(ValueError, match="already claimed"):
        ledger.claim(KEY)


def test_wrapper_anomaly_requires_one_complete_stage_per_expected_tag() -> None:
    tags = (
        "acceptance-abc-starlink-location:latest",
        "acceptance-abc-mission-planner:latest",
    )
    assert reconcile_build(
        124, _complete_two_image_log(), tags, lambda tag: f"sha256:{tag}"
    ).usable

    split_stage = _complete_two_image_log().replace(
        "#10 unpacking to docker.io/library/acceptance-abc-starlink-location:latest\n#10 DONE 0.1s",
        "#11 unpacking to docker.io/library/acceptance-abc-starlink-location:latest\n#12 DONE 0.1s",
    )
    unrelated_done = _complete_two_image_log().replace(
        "#10 DONE 0.1s", "#11 DONE 0.1s", 1
    )
    for output in (split_stage, unrelated_done):
        result = reconcile_build(124, output, tags, lambda tag: f"sha256:{tag}")
        assert not result.usable
        assert result.wrapper_anomaly


def test_real_root_config_uses_public_example_and_retains_only_contract_services(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    topology = render_task_override(
        repository,
        CONTRACT,
        tmp_path,
        "acceptance-realroot",
        _ports(),
        candidate_sha=SHA,
    )

    resolved = resolve_topology(topology, CONTRACT, SubprocessComposeExecutor())

    rendered = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
    assert resolved.project == topology.project
    assert set(rendered["services"]) == set(CONTRACT.services)
    assert '      - ".env"\n' not in topology.root_override_path.read_text(
        encoding="utf-8"
    )
    assert "prometheus" not in rendered["services"]
    assert "grafana" not in rendered["services"]


def test_final_topology_binds_every_contract_service_to_the_exact_candidate_sha(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path, candidate_sha=SHA)
    config = _resolved_config(topology)
    for service in config["services"].values():
        assert isinstance(service, dict)
        service["build"] = {"context": "."}

    resolve_topology(topology, CONTRACT, _executor(config=config))

    rendered = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
    assert topology.candidate_sha == SHA
    assert {
        name: rendered["services"][name]["build"]["args"] for name in CONTRACT.services
    } == {name: {"ACCEPTANCE_CANDIDATE_SHA": SHA} for name in CONTRACT.services}


def test_render_task_override_rejects_invalid_candidate_sha(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="40-character lowercase hexadecimal"):
        _topology(tmp_path, candidate_sha="not-a-candidate")


def test_resolve_rejects_caller_controlled_build_arguments(tmp_path: Path) -> None:
    topology = _topology(tmp_path, candidate_sha=SHA)
    config = _resolved_config(topology)
    for service in config["services"].values():
        assert isinstance(service, dict)
        service["build"] = {"context": ".", "args": {"CALLER": "controlled"}}

    with pytest.raises(ValueError, match="build arguments are not permitted"):
        resolve_topology(topology, CONTRACT, _executor(config=config))


@pytest.mark.parametrize("field", ("cache_from", "cache_to"))
def test_resolve_rejects_caller_controlled_build_cache_authority(
    tmp_path: Path, field: str
) -> None:
    topology = _topology(tmp_path, candidate_sha=SHA)
    config = _resolved_config(topology)
    for service in config["services"].values():
        assert isinstance(service, dict)
        service["build"] = {"context": ".", field: ["type=registry,ref=caller/cache"]}

    with pytest.raises(ValueError, match="cache"):
        resolve_topology(topology, CONTRACT, _executor(config=config))


def test_resolve_rejects_tampered_final_candidate_build_arguments(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path, candidate_sha=SHA)
    executor = _executor(config=_resolved_config(topology))
    original_run = executor._run_default

    def run_tampered_final_config(
        argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if "config" in argv and any(
            Path(item).name == "compose.acceptance.json" for item in argv
        ):
            final = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
            services = final["services"]
            assert isinstance(services, dict)
            for service in services.values():
                assert isinstance(service, dict)
                build = service["build"]
                assert isinstance(build, dict)
                build["args"] = {
                    "ACCEPTANCE_CANDIDATE_SHA": SHA,
                    "INJECTED_AFTER_RENDER": "tampered",
                }
            return CommandResult(0, json.dumps(final))
        return original_run(argv, timeout_seconds=timeout_seconds)

    executor.run_override = lambda argv, timeout_seconds: run_tampered_final_config(
        argv, timeout_seconds=timeout_seconds
    )
    with pytest.raises(ValueError, match="invalid candidate build binding"):
        resolve_topology(topology, CONTRACT, executor)


@pytest.mark.parametrize("field", ("cache_from", "cache_to"))
def test_resolve_rejects_tampered_final_build_cache_authority(
    tmp_path: Path, field: str
) -> None:
    topology = _topology(tmp_path, candidate_sha=SHA)
    executor = _executor(config=_resolved_config(topology))
    original_run = executor._run_default

    def run_tampered_final_config(
        argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if "config" in argv and any(
            Path(item).name == "compose.acceptance.json" for item in argv
        ):
            final = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
            services = final["services"]
            assert isinstance(services, dict)
            for service in services.values():
                assert isinstance(service, dict)
                build = service["build"]
                assert isinstance(build, dict)
                build[field] = ["type=registry,ref=tampered/cache"]
            return CommandResult(0, json.dumps(final))
        return original_run(argv, timeout_seconds=timeout_seconds)

    executor.run_override = lambda argv, timeout_seconds: run_tampered_final_config(
        argv, timeout_seconds=timeout_seconds
    )
    with pytest.raises(ValueError, match="cache"):
        resolve_topology(topology, CONTRACT, executor)


def test_final_build_rejects_candidate_key_mismatch_before_ledger_claim(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path, candidate_sha=SHA)
    executor = _executor(config=_resolved_config(topology))
    ledger = BuildLedger(tmp_path / "ledger")
    mismatched_key = BuildLedgerKey("d" * 40, "b" * 64, "c" * 64)

    resolve_topology(topology, CONTRACT, executor)

    with pytest.raises(ValueError, match="candidate SHA"):
        build_final(topology, PROFILE, CONTRACT, mismatched_key, ledger, executor)
    assert not ledger.root.exists()
    assert not any("build" in call for call in executor.calls)


def test_resolve_rejects_external_resources_and_replaces_inherited_ports(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    root_with_external_resources = _resolved_config(topology)
    root_with_external_resources["networks"] = {
        "starlink-net": {"external": True, "name": "foreign-network"}
    }
    root_with_external_resources["volumes"] = {
        "route_data": {"external": True, "name": "foreign-volume"}
    }
    resolve_topology(topology, CONTRACT, _executor(config=root_with_external_resources))
    rendered = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
    assert rendered["networks"] == {"acceptance": {"name": "acceptance-abc-network"}}
    assert all(
        value["name"].startswith("acceptance-abc-")
        for value in rendered["volumes"].values()
    )

    wrong_port = _resolved_config(topology)
    wrong_port["services"]["starlink-location"]["ports"] = [
        {"host_ip": "127.0.0.1", "published": "18000", "target": 9999}
    ]
    resolve_topology(topology, CONTRACT, _executor(config=wrong_port))
    rendered = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
    assert rendered["services"]["starlink-location"]["ports"] == [
        {
            "host_ip": "127.0.0.1",
            "mode": "ingress",
            "protocol": "tcp",
            "published": "18000",
            "target": 8000,
        }
    ]


def test_resolve_allowlists_task_owned_resources_and_removes_live_root_fields(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    config = _resolved_config(topology)
    backend = config["services"]["starlink-location"]
    assert isinstance(backend, dict)
    backend.update(
        extra_hosts=["dish.starlink:192.168.100.1"],
        restart="unless-stopped",
        volumes=[{"type": "bind", "source": "/host/data", "target": "/data"}],
        secrets=["private"],
    )

    resolve_topology(topology, CONTRACT, _executor(config=config))
    rendered = json.loads(topology.rendered_override_path.read_text(encoding="utf-8"))
    service = rendered["services"]["starlink-location"]
    assert "extra_hosts" not in service
    assert "restart" not in service
    assert "secrets" not in service
    assert all(mount["type"] == "volume" for mount in service["volumes"])
    assert "192.168.100.1" not in json.dumps(rendered)


def test_start_requires_validated_topology_and_usable_matching_ledger(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(
        config=_resolved_config(topology),
        build=CommandResult(0, _complete_two_image_log()),
    )
    ledger = BuildLedger(tmp_path / "ledger")

    with pytest.raises(ValueError, match="validated"):
        start_no_build(topology, CONTRACT, KEY, ledger, executor)

    resolve_topology(topology, CONTRACT, executor)
    with pytest.raises(ValueError, match="usable"):
        start_no_build(topology, CONTRACT, KEY, ledger, executor)

    built = build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor)
    assert built.usable
    start_no_build(topology, CONTRACT, KEY, ledger, executor)
    with pytest.raises(ValueError, match="already claimed"):
        start_no_build(topology, CONTRACT, KEY, ledger, executor)
    assert [call for call in executor.calls if "up" in call] == [
        (*topology.argv, "up", "-d", "--no-build", "--wait", *CONTRACT.services)
    ]


def test_start_no_build_bounds_compose_wait_and_reports_retained_timeout_output(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(
        config=_resolved_config(topology),
        build=CommandResult(0, _complete_two_image_log()),
    )
    ledger = BuildLedger(tmp_path / "ledger")
    resolve_topology(topology, CONTRACT, executor)
    assert build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor).usable
    original_run = executor._run_default

    def run_with_expiring_deadline(
        argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if "up" in argv:
            assert timeout_seconds == 120.0
            raise subprocess.TimeoutExpired(
                argv, timeout_seconds, output="partial startup output"
            )
        return original_run(argv)

    executor.run_override = lambda argv, timeout_seconds: run_with_expiring_deadline(
        argv, timeout_seconds=timeout_seconds
    )

    with pytest.raises(
        ValueError, match="timed out after 120 seconds: partial startup output"
    ):
        start_no_build(topology, CONTRACT, KEY, ledger, executor)


def test_final_build_deadline_closes_ledger_with_bounded_supervision(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(config=_resolved_config(topology))
    ledger = BuildLedger(tmp_path / "ledger")
    resolve_topology(topology, CONTRACT, executor)
    original_run = executor._run_default

    def run_with_expiring_build_deadline(
        argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if "build" in argv:
            assert timeout_seconds is None
            raise BuildSupervisionFailure(
                "build_deadline_exceeded",
                None,
                "partial BuildKit output",
                started_at="2026-09-25T12:00:00+00:00",
                ended_at="2026-09-25T12:30:05+00:00",
                elapsed_seconds=1805.0,
            )
        return original_run(argv, timeout_seconds=timeout_seconds)

    executor.run_override = lambda argv, timeout_seconds: run_with_expiring_build_deadline(
        argv, timeout_seconds=timeout_seconds
    )

    with pytest.raises(BuildSupervisionFailure, match="build_deadline_exceeded"):
        build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor)

    record = ledger.read(KEY)
    assert record["state"] == "closed"
    assert record["reason"] == "build_deadline_exceeded: None"
    assert record["supervision"] == {
        "kind": "build_deadline_exceeded",
        "started_at": "2026-09-25T12:00:00+00:00",
        "ended_at": "2026-09-25T12:30:05+00:00",
        "elapsed_seconds": 1805.0,
        "last_event": None,
    }


def test_final_build_closes_ledger_when_image_reconciliation_raises(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(
        config=_resolved_config(topology),
        build=CommandResult(0, _complete_two_image_log()),
    )
    ledger = BuildLedger(tmp_path / "ledger")
    resolve_topology(topology, CONTRACT, executor)

    def inspect_image_raises(tag: str) -> str | None:
        raise OSError(f"image inspect failed: {tag}")

    executor.inspect_override = inspect_image_raises

    with pytest.raises(OSError, match="image inspect failed"):
        build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor)

    record = ledger.read(KEY)
    assert record["state"] == "closed"
    assert record["image_ids"] == {}
    assert record["reason"] == "final compose build reconciliation failed"


def test_failed_or_stale_build_never_starts(tmp_path: Path) -> None:
    topology = _topology(tmp_path)
    executor = _executor(
        config=_resolved_config(topology), build=CommandResult(1, "#1 ERROR failed")
    )
    ledger = BuildLedger(tmp_path / "ledger")
    resolve_topology(topology, CONTRACT, executor)
    assert not build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor).usable
    with pytest.raises(ValueError, match="usable"):
        start_no_build(topology, CONTRACT, KEY, ledger, executor)

    successful_topology = _topology(tmp_path / "second")
    successful_executor = _executor(
        config=_resolved_config(successful_topology),
        build=CommandResult(0, _complete_two_image_log()),
    )
    successful_ledger = BuildLedger(tmp_path / "second-ledger")
    resolve_topology(successful_topology, CONTRACT, successful_executor)
    assert build_final(
        successful_topology,
        PROFILE,
        CONTRACT,
        KEY,
        successful_ledger,
        successful_executor,
    ).usable
    successful_topology.rendered_override_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        start_no_build(
            successful_topology, CONTRACT, KEY, successful_ledger, successful_executor
        )


def test_contract_only_change_blocks_build_and_no_build_for_same_candidate(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(
        config=_resolved_config(topology),
        build=CommandResult(0, _complete_two_image_log()),
    )
    ledger = BuildLedger(tmp_path / "ledger")
    resolve_topology(topology, CONTRACT, executor)
    changed = ProductContract(**{**CONTRACT.__dict__, "checksum": "d" * 64})
    with pytest.raises(ValueError, match="contract checksum"):
        build_final(topology, PROFILE, changed, KEY, ledger, executor)
    assert build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor).usable
    with pytest.raises(ValueError, match="contract checksum"):
        start_no_build(topology, changed, KEY, ledger, executor)


def test_cleanup_requires_teardown_and_task_resource_absence_preserving_volumes(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(config=_resolved_config(topology))
    cleanup_compose(topology, executor)
    assert (*topology.argv, "down", "--remove-orphans") in executor.calls
    assert all("--volumes" not in call for call in executor.calls)
    assert any(call[:3] == ("docker", "ps", "-aq") for call in executor.calls)
    assert any(call[:3] == ("docker", "network", "ls") for call in executor.calls)

    failed = _executor(
        config=_resolved_config(topology), down=CommandResult(1, "teardown failed")
    )
    with pytest.raises(ValueError, match="teardown failed"):
        cleanup_compose(topology, failed)
    lingering = _executor(
        config=_resolved_config(topology), resources=("container-id", "")
    )
    with pytest.raises(ValueError, match="resources remain"):
        cleanup_compose(topology, lingering)


@dataclass
class _Executor:
    config: dict[str, object]
    build: CommandResult
    down: CommandResult
    resources: tuple[str, str]
    calls: list[tuple[str, ...]]
    run_override: Callable[[tuple[str, ...], float | None], CommandResult] | None = None
    inspect_override: Callable[[str], str | None] | None = None

    def run(
        self, argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if self.run_override is not None:
            return self.run_override(argv, timeout_seconds)
        return self._run_default(argv, timeout_seconds=timeout_seconds)

    def _run_default(
        self, argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        self.calls.append(argv)
        if "config" in argv:
            for item in argv:
                path = Path(item)
                if path.name == "compose.acceptance.json" and path.is_file():
                    return CommandResult(0, path.read_text(encoding="utf-8"))
            return CommandResult(0, json.dumps(self.config))
        if "build" in argv:
            return self.build
        if argv[:3] == ("docker", "ps", "-aq"):
            return CommandResult(0, self.resources[0])
        if argv[:3] == ("docker", "network", "ls"):
            return CommandResult(0, self.resources[1])
        if "down" in argv:
            return self.down
        return CommandResult(0, "")

    def inspect_image(self, tag: str) -> str | None:
        if self.inspect_override is not None:
            return self.inspect_override(tag)
        return f"sha256:{tag}"


def _executor(
    *,
    config: dict[str, object] | None = None,
    build: CommandResult | None = None,
    down: CommandResult | None = None,
    resources: tuple[str, str] = ("", ""),
) -> _Executor:
    return _Executor(
        config or {},
        build or CommandResult(0, ""),
        down or CommandResult(0, ""),
        resources,
        [],
    )


def _ports() -> dict[str, int]:
    return {"starlink-location": 18000, "mission-planner": 18001}


def _topology(tmp_path: Path, *, candidate_sha: str = SHA):
    repository = tmp_path / "repo"
    repository.mkdir(parents=True)
    (repository / ".env.example").write_text("MODE=simulation\n", encoding="utf-8")
    (repository / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    return render_task_override(
        repository,
        CONTRACT,
        tmp_path / "task",
        "acceptance-abc",
        _ports(),
        candidate_sha=candidate_sha,
    )


def _resolved_config(topology) -> dict[str, object]:
    return {
        "name": topology.project,
        "services": {
            "starlink-location": {
                "build": {"context": "."},
                "env_file": [str(topology.env_file)],
                "ports": [
                    {"host_ip": "127.0.0.1", "published": "18000", "target": 8000}
                ],
                "networks": {"starlink-net": {}},
                "volumes": [{"source": "route_data", "target": "/data/routes"}],
            },
            "mission-planner": {
                "build": {"context": "."},
                "env_file": [str(topology.env_file)],
                "ports": [{"host_ip": "127.0.0.1", "published": "18001", "target": 80}],
                "depends_on": {"starlink-location": {"condition": "service_started"}},
                "networks": {"starlink-net": {}},
            },
        },
        "networks": {"starlink-net": {"name": "acceptance-abc-starlink-net"}},
        "volumes": {"route_data": {"name": "acceptance-abc-route_data"}},
    }
