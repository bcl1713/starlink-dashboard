"""One ordinal projection for partial itineraries and legacy legs."""

from dataclasses import dataclass

from .models import PlanningManifest


@dataclass(frozen=True)
class LegOrder:
    executable_ids: tuple[str, ...]
    numbers: dict[str, int]
    total_count: int


def project_leg_order(
    manifest: PlanningManifest | None, legacy_ids: tuple[str, ...]
) -> LegOrder:
    if manifest is None:
        return LegOrder(
            legacy_ids, {key: n for n, key in enumerate(legacy_ids, 1)}, len(legacy_ids)
        )
    manifest = PlanningManifest.model_validate(manifest.storage_record())
    live = sorted(
        (leg for leg in manifest.expected_legs if not leg.retired),
        key=lambda leg: leg.ordinal,
    )
    archived = {leg.installed_leg_id for leg in manifest.expected_legs if leg.retired}
    archived.update(
        item.installed_leg.id
        for item in manifest.leg_history
        if item.reason == "retirement" and item.installed_leg is not None
    )
    numbers = {
        leg.installed_leg_id: leg.ordinal
        for leg in live
        if leg.installed_leg_id in legacy_ids
    }
    remaining = [
        key for key in legacy_ids if key not in numbers and key not in archived
    ]
    numbers.update({key: len(live) + n for n, key in enumerate(remaining, 1)})
    return LegOrder(tuple(numbers), numbers, len(live) + len(remaining))
