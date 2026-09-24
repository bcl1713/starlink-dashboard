from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from acceptance.platform.compose import (
    BuildLedger,
    CommandResult,
    SubprocessComposeExecutor,
    build_final,
    cleanup_compose,
    reconcile_build,
    render_task_override,
    resolve_topology,
    start_no_build,
)
from acceptance.platform.model import (
    BuildLedgerKey,
    PlatformProfile,
    ProductContract,
    RuntimeControl,
    StaticGroup,
)

SHA = "a" * 40
PROFILE = PlatformProfile("platform-v1", "b" * 64, None)  # type: ignore[arg-type]
CONTRACT = ProductContract(
    name="mission-retirement",
    services=("backend", "mission-planner"),
    static_groups=(StaticGroup("unit", Path("."), ("pytest",)),),
    controls=(RuntimeControl("health", "/health", 200),),
    journey_adapter=Path("tools/acceptance/journey.py"),
    assets=(Path("fixtures/example.json"),),
)
KEY = BuildLedgerKey(SHA, "b" * 64, "c" * 64)


def _complete_two_image_log() -> str:
    return """#10 exporting to image
#10 naming to docker.io/library/task-backend:sha
#10 unpacking to docker.io/library/task-backend:sha
#10 DONE 0.1s
#20 exporting to image
#20 naming to docker.io/library/task-mission-planner:sha
#20 unpacking to docker.io/library/task-mission-planner:sha
#20 DONE 0.1s"""


def test_subprocess_executor_streams_combined_output_and_preserves_exit() -> None:
    import sys

    retained: list[str] = []
    result = SubprocessComposeExecutor(retained.append).run(
        (sys.executable, "-c", "import sys; print('plain-buildkit'); sys.exit(124)")
    )

    assert result.returncode == 124
    assert result.output == "plain-buildkit\n"
    assert retained == ["plain-buildkit\n"]


def test_duplicate_build_ledger_claim_is_refused(tmp_path: Path) -> None:
    ledger = BuildLedger(tmp_path)
    ledger.claim(KEY)

    with pytest.raises(ValueError, match="already claimed"):
        ledger.claim(KEY)


def test_timeout_with_complete_images_proceeds_once() -> None:
    result = reconcile_build(
        124,
        _complete_two_image_log(),
        ("task-backend:sha", "task-mission-planner:sha"),
        lambda tag: f"sha256:{tag}",
    )

    assert result.usable is True
    assert result.wrapper_anomaly is True


def test_missing_unpack_or_tag_blocks_startup() -> None:
    result = reconcile_build(
        124,
        _complete_two_image_log().replace("unpacking", "loading", 1),
        ("task-backend:sha", "task-mission-planner:sha"),
        lambda tag: f"sha256:{tag}",
    )

    assert result.usable is False


def test_override_uses_only_public_example_and_resolved_topology_rejects_inherited_state(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / ".env.example").write_text("MODE=simulation\n", encoding="utf-8")
    task_root = tmp_path / "task"
    topology = render_task_override(
        repository,
        CONTRACT,
        task_root,
        "acceptance-abc",
        {"backend": 18000, "mission-planner": 18001},
    )
    override = topology.override_path.read_text(encoding="utf-8")

    assert "container_name: null" in override
    assert str(topology.env_file) in override
    assert "      - .env\n" not in override

    executor = _executor(
        config={
            "name": "acceptance-abc",
            "services": {
                "backend": {
                    "container_name": "acceptance-abc-backend",
                    "env_file": [str(topology.env_file)],
                    "ports": ["127.0.0.1:18000:8000"],
                },
                "mission-planner": {
                    "container_name": "acceptance-abc-mission-planner",
                    "ports": ["127.0.0.1:18001:80"],
                },
            },
            "networks": {"starlink-net": {"name": "acceptance-abc-starlink-net"}},
            "volumes": {"route_data": {"name": "acceptance-abc-route_data"}},
        }
    )
    resolved = resolve_topology(topology, CONTRACT, executor)

    assert resolved.project == "acceptance-abc"
    source_services = executor.config["services"]
    assert isinstance(source_services, dict)
    bad_services = dict(source_services)
    bad_services["backend"] = {"container_name": "backend"}
    with pytest.raises(ValueError, match="fixed|private|namespace"):
        resolve_topology(
            topology,
            CONTRACT,
            _executor(config={**executor.config, "services": bad_services}),
        )

    dependent_services = dict(source_services)
    dependent_services["mission-planner"] = {
        **dependent_services["mission-planner"],
        "depends_on": {"prometheus": {"condition": "service_started"}},
    }
    with pytest.raises(ValueError, match="undeclared dependency"):
        resolve_topology(
            topology,
            CONTRACT,
            _executor(config={**executor.config, "services": dependent_services}),
        )


def test_final_build_is_once_and_start_is_no_build_only(tmp_path: Path) -> None:
    topology = _topology(tmp_path)
    executor = _executor(build=CommandResult(0, _complete_two_image_log()))
    ledger = BuildLedger(tmp_path / "ledger")

    first = build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor)
    second = build_final(topology, PROFILE, CONTRACT, KEY, ledger, executor)
    start_no_build(topology, CONTRACT, executor)
    with pytest.raises(ValueError, match="already claimed"):
        start_no_build(topology, CONTRACT, executor)

    assert first.usable is True
    assert second.usable is False
    assert [command for command in executor.calls if "build" in command] == [
        (*topology.argv, "build", "--no-cache", "--progress=plain", *CONTRACT.services)
    ]
    starts = [command for command in executor.calls if "up" in command]
    assert starts == [
        (*topology.argv, "up", "-d", "--no-build", "--wait", *CONTRACT.services)
    ]
    assert all("--build" not in command for command in executor.calls)


def test_real_build_failure_never_starts_and_cleanup_preserves_volumes(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    executor = _executor(build=CommandResult(1, "#1 ERROR failed"))
    result = build_final(
        topology, PROFILE, CONTRACT, KEY, BuildLedger(tmp_path / "ledger"), executor
    )

    assert result.usable is False
    with pytest.raises(ValueError, match="not usable"):
        start_no_build(topology, CONTRACT, executor, result)
    cleanup_compose(topology, executor)

    assert (*topology.argv, "down", "--remove-orphans") in executor.calls
    assert all("--volumes" not in command for command in executor.calls)


@dataclass
class _Executor:
    config: dict[str, object]
    build: CommandResult
    calls: list[tuple[str, ...]]

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(argv)
        if "config" in argv:
            import json

            return CommandResult(0, json.dumps(self.config))
        if "build" in argv:
            return self.build
        return CommandResult(0, "")

    def inspect_image(self, tag: str) -> str | None:
        return f"sha256:{tag}"


def _executor(
    *, config: dict[str, object] | None = None, build: CommandResult | None = None
) -> _Executor:
    return _Executor(config or {}, build or CommandResult(0, ""), [])


def _topology(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / ".env.example").write_text("MODE=simulation\n", encoding="utf-8")
    return render_task_override(
        repository,
        CONTRACT,
        tmp_path / "task",
        "acceptance-abc",
        {"backend": 18000, "mission-planner": 18001},
    )
