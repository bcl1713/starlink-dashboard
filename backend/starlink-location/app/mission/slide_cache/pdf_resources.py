"""Bounded lossless reuse of identical PDF resources and their dependencies."""

from pypdf import PdfWriter

from app.mission.exporter.export_cancel import check_cancelled


def deduplicate_pdf_resources(writer: PdfWriter, *, cancel=None) -> None:
    # pypdf hashes indirect references before rewiring equal dependencies. A
    # second pass can therefore discover images with now-shared ICC profiles.
    count = sum(obj is not None for obj in writer._objects)
    for _ in range(count + 1):
        check_cancelled(cancel)
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
        check_cancelled(cancel)
        remaining = sum(obj is not None for obj in writer._objects)
        if remaining == count:
            return
        count = remaining
    raise ValueError("PDF resource deduplication failed to converge")
