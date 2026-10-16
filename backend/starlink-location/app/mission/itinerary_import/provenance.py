"""Retained import sources and history validated independently of editing state."""

from app.mission.planning.models import SourceRevision


def imported_sources(mission):
    raw = mission.metadata.get("itinerary_import")
    if raw is None:
        return ()
    if raw.get("version") != 1:
        raise ValueError("Unsupported itinerary import provenance version")
    result = []
    for record in raw.get("source_records", []):
        suffix = "pdf" if record["kind"] == "itinerary_pdf" else "kml"
        source = SourceRevision.model_validate(
            {**record, "owned_relative_path": f"sources/{record['id']}.{suffix}"}
        )
        result.append(source)
    return tuple(result)
