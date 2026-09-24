from __future__ import annotations

import json
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
    services=("starlink-location", "mission-planner"),
    static_groups=(StaticGroup("unit", Path("."), ("pytest",)),),
    controls=(RuntimeControl("health", "/health", 200),),
    journey_adapter=Path("tools/acceptance/journey.py"),
    assets=(Path("fixtures/example.json"),),
)
KEY = BuildLedgerKey(SHA, "b" * 64, "c" * 64)


def _complete_two_image_log(project: str = "acceptance-abc") -> str:
    return f"""#10 exporting to image
#10 naming to docker.io/library/{project}-starlink-location:latest
#10 unpacking to docker.io/library/{project}-starlink-location:latest
#10 DONE 0.1s
#20 exporting to image
#20 naming to docker.io/library/{project}-mission-planner:latest
#20 unpacking to docker.io/library/{project}-mission-planner:latest
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
        repository, CONTRACT, tmp_path, "acceptance-realroot", _ports()
    )

    resolved = resolve_topology(topology, CONTRACT, SubprocessComposeExecutor())

    rendered = json.loads(topology.override_path.read_text(encoding="utf-8"))
    assert resolved.project == topology.project
    assert set(rendered["services"]) == set(CONTRACT.services)
    assert '      - ".env"\n' not in topology.root_override_path.read_text(
        encoding="utf-8"
    )
    assert "prometheus" not in rendered["services"]
    assert "grafana" not in rendered["services"]


def test_resolve_rejects_external_resources_and_replaces_inherited_ports(
    tmp_path: Path,
) -> None:
    topology = _topology(tmp_path)
    external = _resolved_config(topology)
    external["networks"] = {
        "starlink-net": {"external": True, "name": "acceptance-abc-starlink-net"}
    }
    with pytest.raises(ValueError, match="external"):
        resolve_topology(topology, CONTRACT, _executor(config=external))

    external_volume = _resolved_config(topology)
    external_volume["volumes"] = {
        "route_data": {"external": True, "name": "acceptance-abc-route_data"}
    }
    with pytest.raises(ValueError, match="external"):
        resolve_topology(topology, CONTRACT, _executor(config=external_volume))

    foreign_resource = _resolved_config(topology)
    foreign_resource["networks"] = {
        "starlink-net": {"name": "another-project-starlink-net"}
    }
    with pytest.raises(ValueError, match="namespace"):
        resolve_topology(topology, CONTRACT, _executor(config=foreign_resource))

    wrong_port = _resolved_config(topology)
    wrong_port["services"]["starlink-location"]["ports"] = [
        {"host_ip": "127.0.0.1", "published": "18000", "target": 9999}
    ]
    resolve_topology(topology, CONTRACT, _executor(config=wrong_port))
    rendered = json.loads(topology.override_path.read_text(encoding="utf-8"))
    assert rendered["services"]["starlink-location"]["ports"] == [
        {
            "host_ip": "127.0.0.1",
            "mode": "ingress",
            "protocol": "tcp",
            "published": "18000",
            "target": 8000,
        }
    ]


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
    successful_topology.override_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        start_no_build(
            successful_topology, CONTRACT, KEY, successful_ledger, successful_executor
        )


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

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        self.calls.append(argv)
        if "config" in argv:
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


def _topology(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir(parents=True)
    (repository / ".env.example").write_text("MODE=simulation\n", encoding="utf-8")
    (repository / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    return render_task_override(
        repository, CONTRACT, tmp_path / "task", "acceptance-abc", _ports()
    )


def _resolved_config(topology) -> dict[str, object]:
    return {
        "name": topology.project,
        "services": {
            "starlink-location": {
                "env_file": [str(topology.env_file)],
                "ports": [
                    {"host_ip": "127.0.0.1", "published": "18000", "target": 8000}
                ],
                "networks": {"starlink-net": {}},
                "volumes": [{"source": "route_data", "target": "/data/routes"}],
            },
            "mission-planner": {
                "env_file": [str(topology.env_file)],
                "ports": [{"host_ip": "127.0.0.1", "published": "18001", "target": 80}],
                "depends_on": {"starlink-location": {"condition": "service_started"}},
                "networks": {"starlink-net": {}},
            },
        },
        "networks": {"starlink-net": {"name": "acceptance-abc-starlink-net"}},
        "volumes": {"route_data": {"name": "acceptance-abc-route_data"}},
    }
