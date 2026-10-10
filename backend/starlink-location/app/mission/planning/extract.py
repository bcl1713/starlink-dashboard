"""Bounded extraction of the supported rotated flight-planner itinerary table.

Text positions define UTC column regions; local/home cells are never fallbacks.
Source text is retained in typed evidence only, never written to a parser log.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from math import hypot
from uuid import uuid4

from pydantic import ValidationError
from pypdf import PdfReader

from .deadlines import run_bounded
from .models import (
    ExpectedLeg,
    ItineraryAR,
    ItineraryData,
    ItineraryPreview,
    PlanningError,
    SourceEvidence,
)

MAX_PDF_BYTES = 10 * 1024 * 1024
PARSER_SECONDS = 10
DATE_PATTERN = r"\d{1,2}-[A-Za-z]{3}-\d{4}"


class ItineraryExtractionError(ValueError):
    retryable = False

    def __init__(self, message, code="invalid_itinerary_pdf"):
        super().__init__(message)
        self.code = code

    def __reduce__(self):
        return type(self), (str(self), self.code)


@dataclass
class TextToken:
    text: str
    x: float
    y: float


def _rows(page):
    tokens = []

    def visitor(text, cm, tm, font, size):
        if text.strip():
            # Transform text origin by the current content matrix. Page /Rotate
            # changes display only, so table axes remain the source axes.
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            scale = hypot(cm[0], cm[1]) or 1.0
            # Normalize the common content rotation into table axes. The supplied
            # planner rotates text through cm as well as setting page /Rotate.
            axis_x, axis_y = cm[0] / scale, cm[1] / scale
            tokens.append(
                TextToken(
                    " ".join(text.split()),
                    x * axis_x + y * axis_y,
                    -x * axis_y + y * axis_x,
                )
            )

    page.extract_text(visitor_text=visitor)
    groups = []
    for token in sorted(tokens, key=lambda t: (-t.y, t.x)):
        if not groups or abs(groups[-1][0].y - token.y) > 3:
            groups.append([token])
        else:
            groups[-1].append(token)
    return [sorted(row, key=lambda t: t.x) for row in groups]


def _text(row):
    return " ".join(t.text for t in row)


def _utc(date, time):
    return datetime.strptime(
        date + " " + time.rstrip("Z"),
        "%d-%b-%Y %H:%M" if ":" in time else "%d-%b-%Y %H%M",
    ).replace(tzinfo=timezone.utc)


def _parse_itinerary(pdf_bytes):
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise ItineraryExtractionError(
                "Encrypted PDFs are unsupported", "encrypted_pdf"
            )
        pages = [_rows(page) for page in reader.pages]
    except ItineraryExtractionError:
        raise
    except Exception as exc:
        raise ItineraryExtractionError(
            "The itinerary PDF is unreadable", "unreadable_pdf"
        ) from exc
    if not any(pages):
        raise ItineraryExtractionError(
            "Scan-only PDFs require a text-bearing source", "scan_only_pdf"
        )
    document = " ".join(_text(row) for page in pages for row in page)
    if not re.search(r"Mission\s+Itinerary", document, re.IGNORECASE):
        raise ItineraryExtractionError(
            "Unsupported itinerary document format", "unsupported_itinerary_format"
        )
    errors = []
    evidence = []
    legs = []
    active = None
    departure = None
    ar_section = False
    ar_section_has_errors = False
    mission = re.search(
        r"Mission:\s*(.*?)\s+Revision\s*#?:\s*(\d+)", document, re.IGNORECASE
    )
    aircraft = re.search(r"Aircraft:\s*(.*?)\s+Call\s+Sign:", document, re.IGNORECASE)
    call_sign = re.search(r"Call\s+Sign:\s*(\S+)", document, re.IGNORECASE)
    utc_left = utc_right = None
    ar_split = None
    altitude_x = None
    ar_table_left = ar_table_y = None

    def error(code, message, page, row, field):
        errors.append(
            PlanningError(
                code=code,
                message=message,
                source_page=page,
                source_row=row,
                field=field,
            )
        )

    def finish():
        nonlocal active, ar_section, ar_section_has_errors
        if active:
            try:
                legs.append(ExpectedLeg(**active))
            except ValidationError:
                error(
                    "invalid_leg_times",
                    "UTC leg/AR times must increase and ARs must remain inside their leg",
                    active.pop("_page", 1),
                    active.pop("_row", 1),
                    "expected_legs",
                )
            active = None
        ar_section = False
        ar_section_has_errors = False

    for page_number, rows in enumerate(pages, 1):
        for row_number, row in enumerate(rows, 1):
            text = _text(row)
            if "UTC" in text and ("Dep/Arr" in text or "Departure/Arrival" in text):
                # Header may be split into text tokens or emitted as one cell.
                header = next((t for t in row if "Dep/Arr" in t.text), None)
                adj = next(
                    (t for t in row if t.text == "Adj" or t.text.startswith("Adj ")),
                    None,
                )
                if header and adj:
                    utc_left = header.x - 3
                    utc_right = adj.x - 3
            if "Air-to-Air" in text and "Refueling" in text:
                ar_section = True
                ar_split = altitude_x = ar_table_left = ar_table_y = None
                if active:
                    active["ar_section_status"] = "unrecognized"
                continue
            if ar_section and "ARIP" in text and "AREX" in text:
                entry = next((t for t in row if "ARIP" in t.text), None)
                exit = next((t for t in row if "AREX" in t.text), None)
                altitude = next((t for t in row if "Altitude" in t.text), None)
                if entry and exit and altitude:
                    ar_split = (entry.x + exit.x) / 2
                    altitude_x = altitude.x
                    ar_table_left = row[0].x
                    ar_table_y = row[0].y
                continue
            utc_text = _text(
                [t for t in row if utc_left is not None and utc_left <= t.x < utc_right]
            )
            utc_match = re.search(r"(" + DATE_PATTERN + r")\s+(\d{4})(?!\d)", utc_text)
            if utc_match:
                left = [t for t in row if t.x < utc_left]
                airport = next(
                    (
                        re.match(r"([A-Z]{4})\b", t.text).group(1)
                        for t in left
                        if re.match(r"([A-Z]{4})\b", t.text)
                    ),
                    None,
                )
                ordinal = next(
                    (int(t.text) for t in left if t.text.isdigit() and t.x < 80), None
                )
                if airport:
                    evidence.append(
                        SourceEvidence(
                            source_page=page_number,
                            source_row=row_number,
                            source_text=text,
                            field="expected_legs",
                        )
                    )
                    try:
                        timestamp = _utc(*utc_match.groups())
                    except ValueError:
                        error(
                            "invalid_utc",
                            "Invalid UTC leg date/time",
                            page_number,
                            row_number,
                            "expected_legs",
                        )
                        continue
                    if ordinal:
                        finish()
                        departure = (ordinal, airport, timestamp)
                    elif departure:
                        ordinal, dep, start = departure
                        active = {
                            "id": str(uuid4()),
                            "ordinal": ordinal,
                            "departure_airport": dep,
                            "arrival_airport": airport,
                            "departure_time": start,
                            "arrival_time": timestamp,
                            "ar_rows": [],
                            "ar_section_status": "empty",
                        }
                        departure = None
                        ar_section = False
                    continue
            if ar_section and active:
                if re.search(r"\b(None|No ARs?)\b", text, re.IGNORECASE):
                    if not ar_section_has_errors:
                        active["ar_section_status"] = "empty"
                    ar_section = False
                    continue
                # Identify occupied rows below the table header from their
                # track and timing/altitude columns, even if the row label is
                # unreadable. Headers and explicit no-AR text were handled above.
                first = row[0].text if row else ""
                numeric_label = bool(row) and first.isdigit() and row[0].x < 200
                table_row = (
                    ar_table_left is not None
                    and row[0].y < ar_table_y - 3
                    and ar_table_left - 3 <= row[0].x < min(200, altitude_x)
                    and any(token.x >= altitude_x - 3 for token in row)
                )
                if numeric_label or table_row:
                    evidence.append(
                        SourceEvidence(
                            source_page=page_number,
                            source_row=row_number,
                            source_text=text,
                            field="ar_rows",
                        )
                    )
                    if ar_split is None or altitude_x is None:
                        ar_section_has_errors = True
                        active["ar_section_status"] = "unrecognized"
                        error(
                            "unrecognized_ar_section",
                            "AR table columns are unrecognized",
                            page_number,
                            row_number,
                            "ar_rows",
                        )
                        continue
                    if not numeric_label:
                        ar_section_has_errors = True
                        active["ar_section_status"] = "unrecognized"
                        error(
                            "unrecognized_ar_section",
                            "AR row label requires correction",
                            page_number,
                            row_number,
                            "ar_rows",
                        )
                        continue
                    track = next((t.text for t in row[1:] if t.x < altitude_x), None)
                    entry_text = _text(
                        [t for t in row if altitude_x + 25 < t.x < ar_split]
                    )
                    exit_text = _text([t for t in row if t.x >= ar_split])
                    pattern = r"(" + DATE_PATTERN + r")\s+(\d{2}:\d{2}Z)"
                    entry = re.search(pattern, entry_text)
                    exit = re.search(pattern, exit_text)
                    altitude = next(
                        (
                            float(t.text)
                            for t in row
                            if altitude_x - 3 <= t.x <= altitude_x + 25
                            and re.fullmatch(r"\d+(?:\.\d+)?", t.text)
                        ),
                        None,
                    )
                    try:
                        if not entry or not exit or not track:
                            raise ValueError("Incomplete AR row")
                        ar = ItineraryAR(
                            id=str(uuid4()),
                            track=track,
                            source_page=page_number,
                            source_row=row_number,
                            source_text=text,
                            entry_time=_utc(*entry.groups()),
                            exit_time=_utc(*exit.groups()),
                            source_time_precision="minute",
                            source_altitude=altitude,
                        )
                        if (
                            not active["departure_time"]
                            <= ar.entry_time
                            < ar.exit_time
                            <= active["arrival_time"]
                        ):
                            raise ValueError("AR outside leg")
                        active["ar_rows"].append(ar)
                        if not ar_section_has_errors:
                            active["ar_section_status"] = "listed"
                    except (ValueError, ValidationError):
                        ar_section_has_errors = True
                        active["ar_section_status"] = "unrecognized"
                        error(
                            "invalid_ar_utc",
                            "AR entry/exit UTC fields require correction",
                            page_number,
                            row_number,
                            "ar_rows",
                        )
    finish()
    if departure:
        error(
            "incomplete_leg",
            "Departure lacks an arrival UTC row",
            1,
            1,
            "expected_legs",
        )
    if not legs:
        error(
            "unrecognized_utc_table",
            "No complete legs were recognized in UTC columns",
            1,
            1,
            "expected_legs",
        )
    for leg in legs:
        if leg.ar_section_status == "unrecognized" and not errors:
            error(
                "unrecognized_ar_section",
                "AR section requires correction",
                1,
                1,
                "ar_rows",
            )
    if sorted(l.ordinal for l in legs) != list(range(1, len(legs) + 1)):
        error(
            "invalid_leg_order",
            "Expected leg ordinals must be contiguous",
            1,
            1,
            "expected_legs",
        )
    parsed = ItineraryData(
        name=mission.group(1).strip() if mission else "Itinerary",
        itinerary_revision=int(mission.group(2)) if mission else None,
        aircraft=aircraft.group(1).strip() if aircraft else None,
        call_sign=call_sign.group(1) if call_sign else None,
        expected_legs=legs,
    )
    return ItineraryPreview(
        preview_id=str(uuid4()),
        parsed_values=parsed,
        field_errors=errors,
        source_evidence=evidence,
        confirmable=bool(legs) and not errors,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )


def extract_itinerary(pdf_bytes: bytes) -> ItineraryPreview:
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ItineraryExtractionError(
            "PDF exceeds the 10 MiB upload limit", "pdf_too_large"
        )
    return run_bounded(_parse_itinerary, (pdf_bytes,), PARSER_SECONDS)
