"""Compare generated CSV and rendered customer PDF with canonical export evidence."""

import csv
import io
import json
import zipfile
from datetime import datetime


def check_csv(text, intervals):
    rows = list(csv.DictReader(io.StringIO(text)))
    actual = [json.loads(row["Metadata"]).get("planning_interval") for row in rows]
    if actual != intervals:
        raise ValueError("CSV intervals differ from canonical evaluation")
    return True


def verify(package, receipt):
    from pypdf import PdfReader

    with zipfile.ZipFile(package) as archive:
        mission = json.loads(archive.read("mission.json"))
        if mission["id"] != receipt["original_mission_id"] or len(mission["legs"]) != 3:
            raise ValueError("Wrong exported mission")
        evidence = json.loads(
            archive.read("exports/mission/mission-customer-briefing-evidence.json")
        )
        legs = {l["legId"]: l for l in evidence["legs"]}
        pdf_name = next(
            n
            for n in archive.namelist()
            if n.startswith("exports/mission/") and n.endswith(".pdf")
        )
        pdf = PdfReader(io.BytesIO(archive.read(pdf_name)))
        text = " ".join(page.extract_text() or "" for page in pdf.pages)
        if mission["name"] not in text or len(pdf.pages) != len(evidence["pages"]):
            raise ValueError("Rendered PDF does not match briefing evidence")
        for canonical in receipt["legs"]:
            id = canonical["leg_id"]
            intervals = canonical["intervals"]
            check_csv(
                archive.read(f"exports/legs/{id}/timeline.csv").decode(), intervals
            )
            expected = legs[id]
            bounds = expected["canonical"]["utcBounds"]
            parse = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))
            if [parse(t) for t in bounds] != [
                parse(intervals[0]["start_time"]),
                parse(intervals[-1]["end_time"]),
            ]:
                raise ValueError("PDF bounds differ from canonical evaluation")
            for row in expected["customerRows"]:
                for boundary in ("start", "end"):
                    clock = row["clock"][boundary].split()[0]
                    if clock not in text:
                        raise ValueError("Rendered PDF is missing an evidenced clock")
        return {
            "mission_id": mission["id"],
            "csv_legs": len(receipt["legs"]),
            "pdf_pages": len(pdf.pages),
            "canonical_csv_equal": True,
            "rendered_pdf_clocks_equal": True,
        }
