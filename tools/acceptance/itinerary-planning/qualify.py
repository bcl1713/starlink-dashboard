"""Qualify actual package maps and unchanged reviewed inputs inside the candidate."""

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from app.mission import storage
from app.mission.exporter.map_inputs import prepare_map_input
from app.mission.exporter.customer_filename import customer_brief_filename
from map_probe_inputs import package_snapshots
from map_pixels import inspect_pdf_maps

package, output, hashes_path = map(Path, sys.argv[1:4])
output.mkdir(mode=0o700)
source_dir = output / "sources"
source_dir.mkdir()
try:
    hashes = set(json.loads(hashes_path.read_text())["hashes"].values())
    with zipfile.ZipFile(package) as archive:
        metadata = json.loads(archive.read("mission.json"))
        mission = storage.load_mission_v2(metadata["id"])
        assert len(mission.legs) == 3
        for leg in mission.legs:
            actual = json.loads(archive.read(f"legs/{leg.id}.json"))
            assert actual == leg.model_dump(
                mode="json"
            ), "export changed reviewed leg inputs"
            assert leg.is_active is False
        pdf = output / "customer.pdf"
        pdf.write_bytes(
            archive.read("exports/mission/" + customer_brief_filename(metadata["name"]))
        )
        evidence = json.loads(
            archive.read("exports/mission/mission-customer-briefing-evidence.json")
        )
    scenes = {}
    for captured, projected in package_snapshots(package, source_dir, hashes):
        result = prepare_map_input(captured, projected, include_markers=False)
        assert result.scene is not None, result.diagnostics
        scene = result.scene
        leg = json.loads(captured.leg_json)
        scene["endpointLabels"] = {
            "departure": leg.get("departure_airport") or "Departure",
            "arrival": leg.get("arrival_airport") or "Arrival",
        }
        scenes[captured.leg_id] = scene
    assert len(scenes) == 3
    (output / "scenes.json").write_text(json.dumps(scenes))
    (output / "customer-evidence.json").write_text(json.dumps(evidence))
    proof = inspect_pdf_maps(pdf, evidence, output / "maps", scenes)
    assert len(proof) == 3
    (output / "qualification.json").write_text(
        json.dumps(
            {
                "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                "inactive_reviewed_inputs_equal": True,
                "maps": proof,
            },
            indent=2,
        )
    )
finally:
    shutil.rmtree(source_dir)
