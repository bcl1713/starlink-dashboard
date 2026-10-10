"""Legacy documents and original import entries from one captured revision."""

from typing import IO

from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.exporter.snapshot_views import SnapshotViews


def build_snapshot_legacy_package(
    snapshot: ExportSnapshot, *, cancel=None
) -> IO[bytes]:
    from .__main__ import export_mission_package

    views = SnapshotViews(snapshot)
    views.package_payloads()
    return export_mission_package(
        snapshot.mission_id,
        views.route_manager,
        views.poi_manager,
        snapshot=snapshot,
        **({"cancel": cancel} if cancel is not None else {}),
    )
