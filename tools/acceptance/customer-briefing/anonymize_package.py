"""Prepare an existing local mission for private acceptance; never commit its data."""

import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def anonymous(value, prefix):
    return prefix + "-" + hashlib.sha256(value.encode()).hexdigest()[:12]


PUBLIC_SATELLITES = {"X-1", "AOR", "POR", "IOR", "Ku-Leo"}


def clean(value, key="", satellite_names=frozenset()):
    if isinstance(value, dict):
        return {
            k: clean(v, k, satellite_names)
            for k, v in value.items()
            if k not in ("metadata", "notes", "advisories", "description", "remarks")
        }
    if isinstance(value, list):
        return [clean(v, key, satellite_names) for v in value]
    if isinstance(value, str):
        if key in ("initial_x_satellite_id", "target_satellite_id", "satellite_id") or (
            key == "name" and value in satellite_names
        ):
            return value if value in PUBLIC_SATELLITES else anonymous(value, "Label")
        if key == "id" or key.endswith("_id"):
            return anonymous(value, "anon")
        if key == "name" or key.endswith("_name"):
            return anonymous(value, "Label")
        if key in ("reason", "title", "label", "callsign", "mission_number"):
            return "Anonymized source text"
    return value


def anonymize(source, output):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w") as result:
        satellites = (
            json.loads(original.read("pois/satellites.json"))
            if "pois/satellites.json" in original.namelist()
            else {}
        )
        satellite_names = frozenset(p["name"] for p in satellites.get("pois", []))
        mission = clean(
            json.loads(original.read("mission.json")), satellite_names=satellite_names
        )
        mission["name"] = "Anonymized existing mission"
        result.writestr("mission.json", json.dumps(mission))
        for leg in mission["legs"]:
            result.writestr(f'legs/{leg["id"]}.json', json.dumps(leg))
        for path in original.namelist():
            if path.startswith("routes/") and path.endswith(".kml"):
                xml = ET.fromstring(original.read(path))
                for node in xml.iter():
                    tag = node.tag.split("}")[-1]
                    if tag == "name" and node.text:
                        node.text = anonymous(node.text, "Label")
                    elif tag == "description":
                        timing = re.search(
                            r"Time Over Waypoint:\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z",
                            node.text or "",
                        )
                        node.text = timing.group(0) if timing else ""
                    elif tag in ("ExtendedData", "Snippet", "address", "phoneNumber"):
                        node.clear()
                result.writestr(
                    "routes/" + anonymous(Path(path).stem, "anon") + ".kml",
                    ET.tostring(xml, encoding="utf-8", xml_declaration=True),
                )
            elif path.startswith("pois/") and path.endswith(".json"):
                stem = Path(path).stem
                if stem == "satellites":
                    target = "pois/satellites.json"
                elif stem.endswith("-pois"):
                    target = "pois/" + anonymous(stem[:-5], "anon") + "-pois.json"
                else:
                    continue
                result.writestr(
                    target,
                    json.dumps(
                        clean(
                            json.loads(original.read(path)),
                            satellite_names=(
                                satellite_names if stem == "satellites" else frozenset()
                            ),
                        )
                    ),
                )
    return {
        "source_fingerprint": hashlib.sha256(source.read_bytes()).hexdigest(),
        "anonymized_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "mission_id": mission["id"],
        "legs": len(mission["legs"]),
        "selection": "Existing local five-leg package exercises real saved source configuration, long routes and dense coordination",
        "anonymization": "Mission/leg/route/POI identities and human labels/text replaced; public satellite IDs retained and custom satellite references consistently remapped; KML descriptions retain only timing; optional free-text metadata removed",
        "geometry": "retained locally; no customer data committed",
    }
