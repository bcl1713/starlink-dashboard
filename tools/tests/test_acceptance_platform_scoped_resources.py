from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from acceptance.platform.compose import AcceptanceOwnershipLabels, render_task_override
from acceptance.platform.maintenance import (
    DockerImage,
    retain_docker_resources,
    scoped_docker_inventory,
)
from acceptance.platform.model import ProductContract

SHA = "a" * 40


@dataclass
class FakeDocker:
    calls: list[tuple[str, ...]] = field(default_factory=list)
    images: list[DockerImage] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    inspection_overrides: dict[str, DockerImage | None] = field(default_factory=dict)

    def run(self, argv: tuple[str, ...]) -> str:
        self.calls.append(argv)
        return ""

    def list_images(self) -> tuple[DockerImage, ...]:
        return tuple(self.images)

    def inspect_image(self, identifier: str) -> DockerImage | None:
        if identifier in self.inspection_overrides:
            return self.inspection_overrides[identifier]
        return next((image for image in self.images if image.identifier == identifier), None)

    def remove_image(self, identifier: str) -> None:
        self.removed.append(identifier)
        self.images[:] = [image for image in self.images if image.inspected_id != identifier]


def test_final_resources_have_required_labels_and_unlabelled_images_are_inventory_only(
    tmp_path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".env.example").write_text("MODE=simulation\n")
    (repository / "docker-compose.yml").write_text("services: {}\n")
    contract = ProductContract(
        name="resource-labels",
        services=("starlink-location",),
        static_groups=(),
        controls=(),
        journey_adapter=Path("tools/acceptance/journey.py"),
        assets=(),
        checksum="c" * 64,
    )

    topology = render_task_override(
        repository,
        contract,
        tmp_path / "task",
        "acceptance-resource",
        {"starlink-location": 18000},
        candidate_sha=SHA,
        lane="final",
        task_id="task-1",
    )
    docker = FakeDocker()
    inventory = scoped_docker_inventory(docker, topology.docker_labels)

    assert topology.docker_labels == AcceptanceOwnershipLabels(
        lane="final", sha=SHA, task="task-1"
    )
    assert "io.starlink.acceptance.owner=runner" in topology.docker_labels.as_docker_args()
    assert inventory == ()
    assert not any("prune" in argument for call in docker.calls for argument in call)


def test_nonfinal_resources_preserve_exact_lane_and_task_label(tmp_path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".env.example").write_text("MODE=simulation\n")
    (repository / "docker-compose.yml").write_text("services: {}\n")
    contract = ProductContract(
        name="resource-labels",
        services=("starlink-location",),
        static_groups=(),
        controls=(),
        journey_adapter=Path("tools/acceptance/journey.py"),
        assets=(),
        checksum="c" * 64,
    )

    topology = render_task_override(
        repository,
        contract,
        tmp_path / "arbitrary-directory-name",
        "acceptance-resource",
        {"starlink-location": 18000},
        candidate_sha=SHA,
        lane="diagnostic",
        task_id="task-from-wrapper",
    )

    assert topology.docker_labels == AcceptanceOwnershipLabels(
        lane="diagnostic", sha=SHA, task="task-from-wrapper"
    )


def test_successful_image_removal_reinspects_and_observes_exact_id_absent() -> None:
    image = DockerImage(
        identifier="candidate-tag",
        inspected_id="sha256:exact-candidate-id",
        labels=AcceptanceOwnershipLabels("final", SHA, "task-1").values(),
    )
    docker = FakeDocker(images=[image])

    report = retain_docker_resources(docker, {SHA}, apply=True)

    assert report.removed == ("sha256:exact-candidate-id",)
    assert docker.removed == ["sha256:exact-candidate-id"]
    assert docker.inspect_image("candidate-tag") is None


@pytest.mark.parametrize(
    "image",
    (
        DockerImage("tag", "sha256:old", AcceptanceOwnershipLabels("final", SHA, "task").values()),
        DockerImage("tag", "sha256:id", {"io.starlink.acceptance.owner": "runner"}),
        DockerImage("tag", "sha256:id", AcceptanceOwnershipLabels("final", "b" * 40, "task").values()),
        DockerImage(
            "tag",
            "sha256:id",
            AcceptanceOwnershipLabels("final", SHA, "task").values(),
            ledger_references=("protected-ledger",),
        ),
    ),
)
def test_ineligible_or_protected_image_is_not_removed(image: DockerImage) -> None:
    docker = FakeDocker(
        images=[image],
        inspection_overrides={
            "tag": DockerImage("tag", "sha256:new", image.labels),
        },
    )
    if image.inspected_id == "sha256:old":
        docker.inspection_overrides["tag"] = DockerImage(
            image.identifier,
            "sha256:new",
            image.labels,
            image.container_references,
            image.ledger_references,
        )

    report = retain_docker_resources(docker, {SHA}, apply=True)

    assert report.has_anomalies
    assert docker.removed == []


def test_container_or_protected_ledger_reference_blocks_exact_image_removal() -> None:
    labels = AcceptanceOwnershipLabels("final", SHA, "task-1").values()
    image = DockerImage(
        identifier="candidate-tag",
        inspected_id="sha256:exact-candidate-id",
        labels=labels,
        container_references=("container-1",),
        ledger_references=("final-ledger",),
    )
    docker = FakeDocker(images=[image])

    report = retain_docker_resources(docker, {SHA}, apply=True)

    assert report.has_anomalies
    assert docker.removed == []
