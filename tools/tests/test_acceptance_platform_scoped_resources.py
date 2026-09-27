from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
    images: tuple[DockerImage, ...] = ()
    removed: list[str] = field(default_factory=list)

    def run(self, argv: tuple[str, ...]) -> str:
        self.calls.append(argv)
        return ""

    def list_images(self) -> tuple[DockerImage, ...]:
        return self.images

    def inspect_image(self, identifier: str) -> DockerImage | None:
        return next((image for image in self.images if image.identifier == identifier), None)

    def remove_image(self, identifier: str) -> None:
        self.removed.append(identifier)


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


def test_container_or_protected_ledger_reference_blocks_exact_image_removal() -> None:
    labels = AcceptanceOwnershipLabels("final", SHA, "task-1").values()
    image = DockerImage(
        identifier="candidate-tag",
        inspected_id="sha256:exact-candidate-id",
        labels=labels,
        container_references=("container-1",),
        ledger_references=("final-ledger",),
    )
    docker = FakeDocker(images=(image,))

    report = retain_docker_resources(docker, {SHA}, apply=True)

    assert report.has_anomalies
    assert docker.removed == []
