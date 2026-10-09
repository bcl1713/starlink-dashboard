"""Assembled PDFs retain cached content and evidence page order."""

import io
import json
from hashlib import sha256

from tests.unit.test_customer_document import inputs


def test_assembly_preserves_pages_and_rebases_evidence():
    from pypdf import PdfReader, PdfWriter

    from app.mission.slide_cache.assembly import assemble_customer_pdf

    def fragment(leg, widths):
        writer, stream = PdfWriter(), io.BytesIO()
        for width in widths:
            writer.add_blank_page(width=width, height=540)
        writer.write(stream)
        pages = [
            {"page": n, "legId": leg, "rowIds": [f"row-{n}"]}
            for n in range(1, len(widths) + 1)
        ]
        evidence = {
            "legs": [{"legId": leg}],
            "pages": pages,
            "render": {
                "fit": {"pages": pages},
                "maps": {leg: {"status": "ready"}},
                "pdfValidation": {
                    "rows": [{"page": p["page"], "legId": leg} for p in pages]
                },
                "artifactHashes": {"pdfPath": sha256(stream.getvalue()).hexdigest()},
            },
        }
        return {
            "state": "ready",
            "fingerprint": leg,
            "pdf": stream.getvalue(),
            "evidence": json.dumps(evidence).encode(),
        }

    captured = inputs()[0]
    records = {"a": fragment("a", [960, 961]), "b": fragment("b", [962])}
    outcome = assemble_customer_pdf(captured, records, ordered_ids=["b", "a"])
    assert outcome.status == "included"
    reader = PdfReader(io.BytesIO(outcome.artifacts.pdf))
    assert [float(p.mediabox.width) for p in reader.pages] == [962, 960, 961]
    evidence = json.loads(outcome.artifacts.evidence)
    assert [(p["page"], p["legId"]) for p in evidence["pages"]] == [
        (1, "b"),
        (2, "a"),
        (3, "a"),
    ]
    assert [r["page"] for r in evidence["render"]["pdfValidation"]["rows"]] == [1, 2, 3]
    assert (
        evidence["render"]["artifactHashes"]["pdfPath"]
        == sha256(outcome.artifacts.pdf).hexdigest()
    )
    assert evidence["render"]["launchCount"] == 0
    assert evidence["render"]["artifacts"]["pdfPath"] == (
        json.loads(captured.metadata_json)["name"] + "-brief.pdf"
    )


def test_failed_leg_does_not_publish_partial_mission_pdf():
    from app.mission.slide_cache.assembly import assemble_customer_pdf

    outcome = assemble_customer_pdf(
        inputs()[0],
        {"a": {"state": "failed", "warning": "overflow"}},
        ordered_ids=["a"],
    )
    assert outcome.status == "omitted"
    assert outcome.warning_code == "overflow"
    assert outcome.artifacts is None
