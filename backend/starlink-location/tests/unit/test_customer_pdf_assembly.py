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


def test_independent_nested_resources_are_shared_without_merging_unequal_semantics():
    from pypdf import PdfReader, PdfWriter
    from app.mission.slide_cache.assembly import assemble_customer_pdf
    from tests.unit.pdf_resource_fixtures import make_pdf_fragments

    captured, records = make_pdf_fragments()
    baseline = PdfWriter()
    for record in records.values():
        baseline.append(PdfReader(io.BytesIO(record["pdf"])), import_outline=False)
    stream = io.BytesIO()
    baseline.write(stream)
    baseline.close()
    result = assemble_customer_pdf(captured, records)
    reader = PdfReader(io.BytesIO(result.artifacts.pdf))
    assert len(reader.pages) == 5
    assert [p.extract_text() for p in reader.pages] == ["a page 1", "a page 2", "b page 1", "c page 1", "c page 2"]
    assert all(list(p.mediabox) == [0, 0, 960, 540] for p in reader.pages)
    objects = [p["/Resources"]["/XObject"]["/Nested"]["/Resources"]["/XObject"] for p in reader.pages]
    assert len({o.raw_get("/Logo").idnum for o in objects}) == 1
    assert len({o.raw_get("/Map").idnum for o in objects}) == 3
    assert len({o.raw_get("/Masked").idnum for o in objects}) == 3
    assert objects[0].raw_get("/Control").idnum != objects[0].raw_get("/Logo").idnum
    assert len(result.artifacts.pdf) < len(stream.getvalue())
    assert b"orphan must disappear" not in result.artifacts.pdf
    evidence = json.loads(result.artifacts.evidence)
    assert evidence["render"]["artifactHashes"]["pdfPath"] == sha256(result.artifacts.pdf).hexdigest()
    assert [f["render"]["artifactHashes"]["pdfPath"] for f in evidence["render"]["fragments"]] == [sha256(r["pdf"]).hexdigest() for r in records.values()]
    assert [p["page"] for p in evidence["pages"]] == [1, 2, 3, 4, 5]


def test_resource_deduplication_checks_cancellation_before_and_between_passes():
    import pytest
    from pypdf import PdfWriter
    from app.mission.exporter.export_cancel import ExportCancelled
    from app.mission.slide_cache.pdf_resources import deduplicate_pdf_resources

    class Cancel:
        def __init__(self, at):
            self.calls, self.at = 0, at

        def is_set(self):
            self.calls += 1
            return self.calls >= self.at

    for at in [1, 2]:
        writer = PdfWriter()
        writer.add_blank_page(960, 540)
        with pytest.raises(ExportCancelled):
            deduplicate_pdf_resources(writer, cancel=Cancel(at))
        writer.close()
