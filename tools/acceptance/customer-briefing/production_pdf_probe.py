"""Inspect actual API ZIP PDFs using canonical evidence and measured cell bounds."""

import json
import re
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

from PIL import Image
from production_pdf_geometry import geometry_text_hash

from app.mission.exporter.customer_display import display_row
from app.mission.exporter.customer_pdf import verify_customer_pdf

source, destination = map(Path, sys.argv[1:3])
destination.mkdir()
with zipfile.ZipFile(source) as archive:
    pdf = archive.read("exports/mission/mission-customer-briefing-trial.pdf")
    evidence = json.loads(
        archive.read("exports/mission/mission-customer-briefing-evidence.json")
    )
    mission = json.loads(archive.read("mission.json"))
assert mission["id"] == evidence["missionId"]
(destination / "mission-customer-briefing-trial.pdf").write_bytes(pdf)
(destination / "mission-customer-briefing-evidence.json").write_text(
    json.dumps(evidence, indent=2)
)
canonical = {}
for leg in evidence["legs"]:
    for row in leg["customerRows"]:
        clock = row["clock"]
        canonical[leg["legId"], row["id"]] = list(
            display_row(
                {
                    "et": clock["start"] + "–" + clock["end"],
                    "impact": row["impact"],
                    "remaining": row["remaining"],
                    "posture": row["posture"],
                }
            )
        )
expected = {
    "schemaVersion": 1,
    "pageCount": len(evidence["pages"]),
    "pageSizePt": [960, 540],
    "pages": [],
    "rows": [],
}
for page, measured in zip(evidence["pages"], evidence["render"]["fit"]["pages"]):
    geometry = measured["pdfMeasured"]
    expected["pages"].append(
        {
            "page": page["page"],
            **{
                key.replace("Px", "Pt"): [v * 0.75 for v in value] if value else None
                for key, value in geometry.items()
                if key != "rows"
            },
        }
    )
    assert [r["id"] for r in geometry["rows"]] == page["rowIds"]
    for row in geometry["rows"]:
        expected["rows"].append(
            {
                "page": page["page"],
                "legId": page["legId"],
                "rowId": row["id"],
                "displayCells": canonical[page["legId"], row["id"]],
                "cellBoundsPt": [
                    [v * 0.75 for v in box] for box in row["cellBoundsPx"]
                ],
            }
        )
pdf_path = destination / "mission-customer-briefing-trial.pdf"
proof = verify_customer_pdf(pdf_path, expected, timeout_seconds=30)
assert proof == evidence["render"]["pdfValidation"]
(destination / "actual-pdf-proof.json").write_text(json.dumps(proof, indent=2))
rasters = {}
for mode in ("color", "grayscale"):
    prefix = destination / ("pdf-" + mode)
    command = ["pdftoppm", "-r", "240", "-png"]
    if mode == "grayscale":
        command.append("-gray")
    subprocess.run([*command, str(pdf_path), str(prefix)], check=True, timeout=60)
    files = sorted(destination.glob(f"pdf-{mode}-*.png"))
    assert len(files) == proof["pageCount"]
    rasters[mode] = []
    for file in files:
        with Image.open(file) as image:
            assert image.size == (3200, 1800)
            rasters[mode].append(
                {
                    "file": file.name,
                    "pixelHash": sha256(image.convert("RGBA").tobytes()).hexdigest(),
                }
            )
normalized = re.sub(
    rb"/(CreationDate|ModDate)\s*\(D:[^)]*\)", rb"/\1 (D:normalized)", pdf
)
normalized = re.sub(
    rb"/ID\s*\[\s*<[^>]*>\s*<[^>]*>\s*\]", b"/ID [normalized]", normalized
)
text = subprocess.check_output(
    ["pdftotext", "-bbox-layout", str(pdf_path), "-"], text=True, timeout=20
)
result = {
    "pageCount": proof["pageCount"],
    "rowCount": len(proof["rows"]),
    "snapshotFingerprint": evidence["snapshotFingerprint"],
    "normalizedPdfHash": sha256(normalized).hexdigest(),
    "geometryTextHash": geometry_text_hash(text),
    "excludedGeometryMetadata": ["CreationDate", "ModDate"],
    "rasters": rasters,
}
(destination / "inspection.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
