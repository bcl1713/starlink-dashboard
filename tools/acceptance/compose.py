"""Isolated Compose commands and strict BuildKit completion reconciliation."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .artifacts import EvidenceWriter
from .model import AcceptanceInputs, AcceptancePhase, PhaseResult

_TAG_PREFIX = "accept-"
_STAGE = re.compile(r"^#(?P<stage>\d+) (?P<message>.*)$")


@dataclass(frozen=True)
class ImageRecord:
    """The BuildKit completion signals observed for one expected image tag."""

    tag: str
    exported: bool
    named: bool
    unpacked: bool
    done: bool

    @property
    def complete(self) -> bool:
        return self.exported and self.named and self.unpacked and self.done


@dataclass(frozen=True)
class BuildDisposition:
    """A build outcome after comparing wrapper status to tangible images."""

    usable: bool
    wrapper_anomaly: bool
    detail: str


def project_name(inputs: AcceptanceInputs) -> str:
    return f"{_TAG_PREFIX}{inputs.sha[:12]}"


def image_tags(inputs: AcceptanceInputs) -> tuple[str, str]:
    suffix = inputs.sha[:12]
    return (f"accept-backend:{suffix}", f"accept-frontend:{suffix}")


def render_override(inputs: AcceptanceInputs) -> str:
    """Render a self-contained, non-secret two-service Compose override."""
    backend_tag, frontend_tag = image_tags(inputs)
    data_root = (inputs.evidence_root / inputs.sha / "compose-data").as_posix()
    return "\n".join(
        (
            "services: !override",
            "  starlink-location:",
            "    image: " + backend_tag,
            "    build: ./backend/starlink-location",
            "    environment:",
            "      - STARLINK_MODE=simulation",
            "      - SIMULATION_MODE=true",
            "    ports: !override []",
            "    volumes: !override",
            f"      - {data_root}/missions:/app/data/missions",
            f"      - {data_root}/satellites:/app/data/satellites",
            f"      - {data_root}/coverage:/app/data/sat_coverage",
            "  mission-planner:",
            "    image: " + frontend_tag,
            "    build:",
            "      context: ./frontend/mission-planner",
            "      dockerfile: Dockerfile",
            "    ports: !override []",
            "    depends_on:",
            "      starlink-location:",
            "        condition: service_started",
            "",
        )
    )


def compose_build_argv(
    inputs: AcceptanceInputs, compose_files: Sequence[Path]
) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        project_name(inputs),
        *[item for path in compose_files for item in ("--file", str(path))],
        "build",
        "--no-cache",
        "--progress=plain",
        "starlink-location",
        "mission-planner",
    ]


def parse_buildkit_log(text: str, expected_tags: Sequence[str]) -> list[ImageRecord]:
    """Require export, naming, unpack, and final DONE in one BuildKit stage."""
    stages: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = _STAGE.match(line)
        if match:
            stages.setdefault(match["stage"], []).append(match["message"])
    records: list[ImageRecord] = []
    for tag in expected_tags:
        tag_stages = [
            messages
            for messages in stages.values()
            if any("naming to " in line and tag in line for line in messages)
        ]
        messages = tag_stages[0] if len(tag_stages) == 1 else []
        records.append(
            ImageRecord(
                tag=tag,
                exported=any(
                    line.startswith("exporting to image") for line in messages
                ),
                named=any("naming to " in line and tag in line for line in messages),
                unpacked=any(
                    "unpacking to " in line and tag in line for line in messages
                ),
                done=any(line.startswith("DONE") for line in messages),
            )
        )
    return records


def reconcile_build(
    returncode: int,
    log_text: str,
    expected_tags: Sequence[str],
    inspect_tag: Callable[[str], str],
) -> BuildDisposition:
    records = parse_buildkit_log(log_text, expected_tags)
    completed = all(record.complete for record in records)
    image_ids = [inspect_tag(tag).strip() for tag in expected_tags] if completed else []
    images_exist = all(image_id.startswith("sha256:") for image_id in image_ids)
    usable = completed and images_exist
    if returncode == 0:
        return BuildDisposition(
            usable, False, "BuildKit output and image inspection reconciled"
        )
    if usable:
        return BuildDisposition(
            True, True, "wrapper returned nonzero after complete images"
        )
    return BuildDisposition(False, False, "build did not produce every completed image")


def run_full_build(inputs: AcceptanceInputs, writer: EvidenceWriter) -> PhaseResult:
    """Build only the isolated services; never start a stack after a failure."""
    result = subprocess.run(
        compose_build_argv(inputs, [Path("docker-compose.yml")]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    log_text = result.stdout or ""
    writer.record_text(Path("build.log"), log_text)
    tags = image_tags(inputs)
    disposition = reconcile_build(result.returncode, log_text, tags, _inspect_tag)
    status = "passed" if disposition.usable else "failed"
    return PhaseResult(AcceptancePhase.FULL, status, detail=disposition.detail)


build_full = run_full_build


def start_no_build(
    inputs: AcceptanceInputs, compose_files: Sequence[Path]
) -> subprocess.CompletedProcess[str]:
    return _compose_run(
        inputs,
        compose_files,
        ["up", "--no-build", "--detach", "starlink-location", "mission-planner"],
    )


def runtime_controls(
    inputs: AcceptanceInputs, compose_files: Sequence[Path], command: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    return _compose_run(inputs, compose_files, list(command))


def cleanup_compose(
    inputs: AcceptanceInputs, compose_files: Sequence[Path]
) -> subprocess.CompletedProcess[str]:
    return _compose_run(
        inputs, compose_files, ["down", "--volumes", "--remove-orphans"]
    )


def _inspect_tag(tag: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", tag],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _compose_run(
    inputs: AcceptanceInputs, compose_files: Sequence[Path], command: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    argv = [
        "docker",
        "compose",
        "--project-name",
        project_name(inputs),
        *[item for path in compose_files for item in ("--file", str(path))],
        *command,
    ]
    return subprocess.run(argv, text=True, check=False, capture_output=True)
