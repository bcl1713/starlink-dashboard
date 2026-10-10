"""Synthetic text-table PDFs; no operational source contents."""

from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.mission.planning.extract import ItineraryExtractionError, extract_itinerary


def synthetic_pdf(
    *,
    unknown=False,
    unknown_rows=False,
    unreadable_ar_label=None,
    blank=False,
    encrypted=False,
):
    writer = PdfWriter()
    page = writer.add_blank_page(width=800, height=600)
    page.rotate(90)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    commands = []

    def line(y, *cells):
        for x, text in cells:
            commands.append(f"BT /F1 9 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET")

    if not blank:
        line(
            570,
            (80, "Mission Itinerary"),
            (280, "Mission: SYNTH Revision #: 5 Aircraft: DEMO Call Sign: TEST"),
        )
        line(
            545,
            (65, "Departure/Arrival Airport"),
            (245, "Dep/Arr"),
            (280, "Date"),
            (302, r"\(UTC\)"),
            (345, "Adj"),
            (395, r"Dep/Arr Date \(L\)"),
            (625, "Home Dep/Arr"),
        )
        y = 520
        specs = [
            (
                "AAAA",
                "BBBB",
                "25-Oct-2026",
                "1300",
                "26-Oct-2026",
                "0400",
                [
                    ("AR106LW", "25-Oct-2026", "14:26Z", "25-Oct-2026", "15:23Z"),
                    ("GRIZZ-W", "25-Oct-2026", "19:20Z", "25-Oct-2026", "20:33Z"),
                    ("TROJAN-W", "26-Oct-2026", "00:47Z", "26-Oct-2026", "02:08Z"),
                ],
            ),
            ("BBBB", "CCCC", "27-Oct-2026", "1000", "27-Oct-2026", "1200", []),
            (
                "CCCC",
                "AAAA",
                "29-Oct-2026",
                "1700",
                "30-Oct-2026",
                "0200",
                [
                    ("TITAN-E", "29-Oct-2026", "18:18Z", "29-Oct-2026", "19:50Z"),
                    ("GRIZZ-E", "29-Oct-2026", "22:58Z", "30-Oct-2026", "00:05Z"),
                ],
            ),
        ]
        for ordinal, (dep, arr, dd, dt, ad, at, ars) in enumerate(specs, 1):
            line(
                y,
                (55, str(ordinal)),
                (70, dep),
                (250, dd),
                (303, dt),
                (395, "31-Dec-2030"),
                (455, "2359"),
                (625, "01-Jan-2031"),
                (680, "1111"),
            )
            y -= 15
            line(
                y, (70, arr), (250, ad), (303, at), (395, "31-Dec-2030"), (455, "2359")
            )
            y -= 15
            if ars:
                line(y, (340, "Air-to-Air Refueling Details"))
                y -= 15
                line(
                    y,
                    (110, "AR # Track Details"),
                    (417, "Altitude"),
                    (516, "ARIP"),
                    (636, "AREX"),
                )
                y -= 15
                for i, (track, d1, t1, d2, t2) in enumerate(ars, 1):
                    line(
                        y,
                        (
                            115,
                            (
                                "?"
                                if unknown_rows or unreadable_ar_label == (ordinal, i)
                                else str(i)
                            ),
                        ),
                        (140, track),
                        (419, "210"),
                        (489, d1),
                        (537, t1 if not unknown else "UNKNOWN"),
                        (610, d2),
                        (660, t2),
                    )
                    y -= 15
        line(
            y - 5,
            (80, "Total"),
            (140, "Planned Flight Time"),
            (489, "06:00"),
            (610, "hours"),
        )
    stream = DecodedStreamObject()
    stream.set_data(("q 0 1 -1 0 600 0 cm\n" + "\n".join(commands) + "\nQ").encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("secret")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def test_rotated_utc_columns_and_five_ar_windows():
    preview = extract_itinerary(synthetic_pdf())
    assert preview.confirmable
    assert not preview.field_errors
    legs = preview.parsed_values.expected_legs
    assert [len(leg.ar_rows) for leg in legs] == [3, 0, 2]
    assert legs[0].departure_time.year == 2026
    assert legs[2].ar_rows[1].exit_time.date() > legs[2].ar_rows[1].entry_time.date()
    assert legs[0].ar_rows[0].source_altitude == 210
    assert legs[0].ar_rows[0].confirmed_units is None
    assert preview.source_evidence and legs[0].ar_rows[0].source_page == 1


def test_unknown_ar_section_is_not_empty():
    preview = extract_itinerary(synthetic_pdf(unknown=True))
    assert preview.field_errors and not preview.confirmable
    assert preview.parsed_values.expected_legs[0].ar_section_status == "unrecognized"


@pytest.mark.parametrize(
    "kwargs,code",
    [({"blank": True}, "scan_only_pdf"), ({"encrypted": True}, "encrypted_pdf")],
)
def test_scan_only_is_rejected(kwargs, code):
    with pytest.raises(ItineraryExtractionError) as e:
        extract_itinerary(synthetic_pdf(**kwargs))
    assert e.value.code == code


def test_pdf_size_rejected_before_parsing():
    with pytest.raises(ItineraryExtractionError, match="10 MiB"):
        extract_itinerary(b"x" * (10 * 1024 * 1024 + 1))


def test_unknown_ar_header_without_rows_requires_correction():
    preview = extract_itinerary(synthetic_pdf(unknown_rows=True))
    assert not preview.confirmable
    assert len(preview.parsed_values.expected_legs) == 3
    assert [leg.ar_section_status for leg in preview.parsed_values.expected_legs] == [
        "unrecognized",
        "empty",
        "unrecognized",
    ]
    assert any(
        error.code == "unrecognized_ar_section" for error in preview.field_errors
    )


def test_explicit_empty_ar_section():
    writer = PdfWriter()
    writer.append(BytesIO(synthetic_pdf()))
    page = writer.pages[0]
    content = page.get_contents().get_data()
    # Insert an explicit empty section after leg 2 arrival, before leg 3.
    marker = b"BT /F1 9 Tf 1 0 0 1 55 385 Tm"
    inserted = b"BT /F1 9 Tf 1 0 0 1 340 395 Tm (Air-to-Air Refueling Details) Tj ET\nBT /F1 9 Tf 1 0 0 1 110 390 Tm (No ARs) Tj ET\n"
    assert marker in content
    content = content.replace(marker, inserted + marker)
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    preview = extract_itinerary(out.getvalue())
    assert preview.confirmable
    assert preview.parsed_values.expected_legs[1].ar_section_status == "empty"


@pytest.mark.parametrize("unreadable_row", [1, 2, 3])
def test_mixed_readable_and_unreadable_ar_rows_block_confirmation(unreadable_row):
    preview = extract_itinerary(synthetic_pdf(unreadable_ar_label=(1, unreadable_row)))
    assert not preview.confirmable
    assert preview.parsed_values.expected_legs[0].ar_section_status == "unrecognized"
    assert preview.parsed_values.expected_legs[2].ar_section_status == "listed"
    rows = [e for e in preview.source_evidence if e.field == "ar_rows"]
    assert len(rows) == 5
    unknown = next(e for e in rows if e.source_text.startswith("? "))
    assert any(
        e.field == "ar_rows"
        and e.source_page == unknown.source_page
        and e.source_row == unknown.source_row
        for e in preview.field_errors
    )
    assert len(preview.parsed_values.expected_legs[0].ar_rows) == 2
