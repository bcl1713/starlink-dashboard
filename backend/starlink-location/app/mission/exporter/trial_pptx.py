"""Standalone editable customer briefing. No package integration or storage IO."""

from __future__ import annotations

import io
import json
import re
import zipfile
from itertools import pairwise
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_PATTERN
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.util import Inches, Pt

from .snapshot import ExportSnapshot
from .trial_clocks import format_clocks
from .trial_layout import (
    COLUMN_WIDTHS,
    COLUMNS,
    HEIGHT,
    INK,
    LANE_HEIGHTS,
    LANES,
    NEUTRAL,
    POSTURE_COLORS,
    WIDTH,
    chunks,
    line_height,
    measured_width,
    style_frame,
    text_height,
    textbox,
    wrap,
)
from .trial_maps import LegMapResult
from .trial_projection import TRANSPORT_NAMES, TrialLeg

ASSET = Path(__file__).resolve().parents[1] / "assets/APO Patch.jpg"
LEGEND = (
    "Up: usable · Down: hatched · ?: indeterminate · SOF / AR: coordination restriction"
)
POSTURE_LEGEND = "Up: 3 Nominal · 2 Degraded · 1 Limited / elevated risk\n0 Communications unavailable · ? Posture uncertain"
IMPLICATIONS = {
    "Nominal": "Three transports usable.",
    "Degraded": "Two transports remain; reduced redundancy.",
    "Limited / elevated risk": "One transport remains; elevated risk.",
    "Communications unavailable": "All three transports independently unavailable.",
    "Posture uncertain": "Known usable transports listed; unresolved usability requires review.",
}


class TrialGenerationError(RuntimeError):
    """The complete trial deck could not be generated and validated."""


def _picture(slide, name, data, x, y, width, height):
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        w, h = image.size
    scale = min(width / w, height / h)
    picture = slide.shapes.add_picture(
        io.BytesIO(data),
        Inches(x + (width - w * scale) / 2),
        Inches(y + (height - h * scale) / 2),
        width=Inches(w * scale),
        height=Inches(h * scale),
    )
    picture.name = name


def _clocks(timestamp, leg):
    clock = format_clocks(timestamp, leg.utc_bounds[0] if leg.utc_bounds else timestamp)
    relative = clock.relative if leg.utc_bounds else "T-zero unavailable"
    return f"{clock.et}\n{clock.zulu} · {relative}"


def _locations(captured):
    raw = json.loads(captured.leg_json)
    route = (
        json.loads(captured.effective_route_json)
        if captured.effective_route_json
        else {}
    )
    points = route.get("points") or []
    locations = []
    missing = False
    for key, index in (("departure_airport", 0), ("arrival_airport", -1)):
        location = raw.get(key)
        if not location:
            missing = True
            point = points[index] if points else {}
            location = (
                point.get("name")
                or point.get("label")
                or route.get("metadata", {}).get("name")
                or raw.get("name")
                or captured.leg_id
            )
        locations.append(str(location))
    return locations, missing


def _page(prs, captured, leg, n, total, kind, title):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.name = f"{kind}:{leg.leg_id}:{len(prs.slides)}"
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(255, 255, 255)
    _picture(slide, "apo-patch", ASSET.read_bytes(), 12.45, 0.18, 0.52, 0.52)
    textbox(
        slide,
        "heading",
        "Customer briefing — Trial",
        0.35,
        0.12,
        4.55,
        size=18,
        bold=True,
    )
    textbox(slide, "support:posture", POSTURE_LEGEND, 5.05, 0.10, 7.2, 0.55, size=14)
    locations, _missing = _locations(captured)
    textbox(
        slide,
        "leg-heading",
        f"Leg {n} of {total} · {locations[0]} → {locations[1]}",
        0.35,
        0.62,
        12.6,
        1.0,
        size=20,
        bold=True,
    )
    if leg.utc_bounds:
        start, end = leg.utc_bounds
        hours, seconds = divmod(int((end - start).total_seconds()), 3600)
        minutes, seconds = divmod(seconds, 60)
        duration = f"{hours}h {minutes:02d}m" + (f" {seconds:02d}s" if seconds else "")
        # Dates and offsets are always explicit, even on repeated DST clocks.
        textbox(
            slide,
            "time:flight",
            f"Departure {format_clocks(start, start).et} · Arrival {format_clocks(end, start).et} · Flight {duration}",
            0.35,
            1.38,
            12.6,
            0.55,
            size=20,
        )
        textbox(
            slide,
            "support:clocks",
            f"Zulu {format_clocks(start, start).zulu} → {format_clocks(end, start).zulu} · {format_clocks(start, start).relative} → {format_clocks(end, start).relative} · Planned departure basis",
            0.35,
            6.76,
            12.6,
            0.36,
            size=14,
        )
    else:
        textbox(
            slide,
            "time:missing",
            "Flight timing unavailable — incomplete leg data",
            0.35,
            1.38,
            12.6,
            size=20,
        )
    textbox(slide, "legend", LEGEND, 0.35, 6.34, 12.6, 0.40, size=18)
    textbox(
        slide,
        "support:caveat",
        f"{leg.prediction_caveat} · Page {len(prs.slides)}"
        + (" · continued" if "continued" in title else ""),
        0.35,
        7.12,
        12.6,
        0.36,
        size=14,
    )
    return slide


def _rect(slide, name, x, y, w, h, color, pattern=None):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), max(1, Inches(w)), Inches(h)
    )
    shape.name = name
    if pattern:
        shape.fill.patterned()
        shape.fill.pattern = pattern
        shape.fill.fore_color.rgb = RGBColor.from_string("727B84")
        shape.fill.back_color.rgb = RGBColor.from_string(NEUTRAL)
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(color)
    shape.line.color.rgb = RGBColor.from_string("FFFFFF")
    shape.line.width = Inches(0.008)
    return shape


def _map(slide, result, view):
    if view:
        _picture(slide, f"map:{view.id}", view.png, 10.15, 2.15, 2.75, 1.65)
        label = f"{view.id}\n{result.label}"
    else:
        label = f"Route map unavailable\n{result.endpoints[0]} → {result.endpoints[1]}\n{result.reason or 'Captured route image unavailable'}"
    # Map captions are supporting references, while fallbacks remain explicit.
    parts = chunks(label, 2.75, 14, 1.90)
    textbox(slide, "support:map", parts[0], 10.15, 3.85, 2.75, size=14, wrapped=False)
    return parts[1:]


def _timeline(prs, captured, leg, result, n, total):
    panels = tuple(leg.intervals[i : i + 4] for i in range(0, len(leg.intervals), 4))
    for index, intervals in enumerate(panels):
        slide = _page(
            prs,
            captured,
            leg,
            n,
            total,
            "timeline",
            f"Timeline panel {index + 1} of {len(panels)}"
            + (" · continued" if index else ""),
        )
        start, end = intervals[0].start_time, intervals[-1].end_time
        support = next(sh for sh in slide.shapes if sh.name == "support:clocks")
        a, b = format_clocks(start, leg.utc_bounds[0]), format_clocks(
            end, leg.utc_bounds[0]
        )
        style_frame(
            support.text_frame,
            f"Panel Zulu {a.zulu} → {b.zulu} · {a.relative} → {b.relative} · Planned departure basis",
            14,
        )
        x, width = 3.7, 6.1
        textbox(
            slide,
            "time:panel-start",
            format_clocks(start, leg.utc_bounds[0]).et.replace(" ", "\n", 1),
            x,
            1.95,
            3.3,
            0.93,
            size=20,
            wrapped=False,
        )
        textbox(
            slide,
            "time:panel-end",
            format_clocks(end, leg.utc_bounds[0]).et.replace(" ", "\n", 1),
            x + width - 3.2,
            1.95,
            3.3,
            0.93,
            size=20,
            wrapped=False,
        )
        y = 2.83
        for lane, (label, h) in enumerate(zip(LANES, LANE_HEIGHTS)):
            textbox(
                slide, f"lane:{lane}", label, 0.35, y, 3.3, h, size=18, bold=lane == 0
            )
            for interval in intervals:
                left = x + width * ((interval.start_time - start) / (end - start))
                bar_width = width * (
                    (interval.end_time - interval.start_time) / (end - start)
                )
                pattern = None
                if lane == 0:
                    value = interval.posture
                    color = POSTURE_COLORS[value]
                    if value == "Posture uncertain":
                        pattern = MSO_PATTERN.LIGHT_DOWNWARD_DIAGONAL
                elif lane < 4:
                    value = interval.decisions[lane - 1].value
                    color = NEUTRAL
                    if value in ("Down", "?"):
                        pattern = MSO_PATTERN.LIGHT_DOWNWARD_DIAGONAL
                else:
                    kinds = tuple(
                        dict.fromkeys(
                            "SOF" if r.kind == "sof" else "AR"
                            for r in interval.restrictions
                        )
                    )
                    value = " + ".join(kinds)
                    color = NEUTRAL
                    if kinds:
                        pattern = MSO_PATTERN.SMALL_GRID
                bar = _rect(
                    slide,
                    f"bar:{interval.id}:{lane}",
                    left,
                    y,
                    bar_width,
                    h,
                    color,
                    pattern,
                )
                # Narrow intervals keep true proportional widths. Their label
                # lives in the linked callout and editable window table.
                size = 18
                if lane == 0 and measured_width(value, size, True) + 0.2 >= bar_width:
                    value = (
                        "?"
                        if interval.posture == "Posture uncertain"
                        else f"{sum(d.value == 'Up' for d in interval.decisions)} Up"
                    )
                if value and measured_width(value, size, lane == 0) + 0.2 < bar_width:
                    style_frame(
                        bar.text_frame,
                        value,
                        size,
                        lane == 0,
                        (
                            "FFFFFF"
                            if lane == 0
                            and interval.posture
                            in ("Nominal", "Communications unavailable")
                            else INK
                        ),
                    )
            y += h
        # Non-overlapping numbered callouts connect to exact interval starts.
        for slot, interval in enumerate(intervals):
            target = x + width * ((interval.start_time - start) / (end - start))
            label_x = x + slot * width / len(intervals)
            connector = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                Inches(target),
                Inches(5.85),
                Inches(label_x + 0.25),
                Inches(5.93),
            )
            connector.name = f"callout:{interval.id}"
            connector.line.color.rgb = RGBColor.from_string(INK)
            textbox(
                slide,
                f"window:{interval.id}",
                f"W{interval.window_number}",
                label_x,
                5.91,
                width / len(intervals),
                0.40,
                size=20,
                bold=True,
            )
        view = result.views[index % len(result.views)] if result.views else None
        overflow = _map(slide, result, view)
        for part in overflow:
            extra = _page(
                prs, captured, leg, n, total, "map-detail", "Map context · continued"
            )
            textbox(extra, "map-detail", part, 0.35, 2.15, 12.6, size=18)
    # Every provided hemisphere view is embedded, including those beyond the
    # number of timeline panels; no network relationships or blank map pages.
    for view in result.views[len(panels) :]:
        slide = _page(
            prs, captured, leg, n, total, "map-view", f"Route context · {view.id}"
        )
        _picture(slide, f"map:{view.id}", view.png, 0.5, 2.05, 9.3, 3.8)
        textbox(
            slide, "support:map", f"{view.id}\n{result.label}", 10.0, 2.15, 2.9, size=14
        )


def _row_text(interval):
    down = [
        name
        for name, d in zip(TRANSPORT_NAMES, interval.decisions)
        if d.value == "Down"
    ]
    unknown = [
        name for name, d in zip(TRANSPORT_NAMES, interval.decisions) if d.value == "?"
    ]
    facts = [f"Window {interval.window_number}", interval.id]
    if down:
        facts.append("Down: " + ", ".join(down))
    if unknown:
        facts.append("Indeterminate: " + ", ".join(unknown))
    facts += list(dict.fromkeys((*interval.causes, *interval.limitations)))
    if interval.active_source_ids:
        facts.append("Sources: " + ", ".join(interval.active_source_ids))
    remaining = "\n".join(interval.remaining_transports) or (
        "None known; usability unresolved" if unknown else "None"
    )
    count = sum(d.value == "Up" for d in interval.decisions)
    posture = f"{interval.posture}\n{count} known Up\n{IMPLICATIONS[interval.posture]}"
    return "\n".join(facts), remaining, posture


def _table(prs, captured, leg, result, n, total):
    # Unresolved timing and provenance notes precede all timed rows, in full.
    location_note = (
        ("Endpoint names unavailable; captured route / leg names shown",)
        if _locations(captured)[1]
        else ()
    )
    notes = (
        *location_note,
        *leg.notes,
        leg.prediction_caveat,
        *result.warnings,
        leg.planned_departure_basis,
        *((leg.quiet_summary,) if leg.quiet_summary else ()),
    )
    for note in ("\n\n".join(dict.fromkeys(notes)),):
        for part in chunks(note, 12.6, 18, 3.8):
            slide = _page(
                prs,
                captured,
                leg,
                n,
                total,
                "coordination-notes",
                "Coordination notes / planned basis",
            )
            textbox(slide, "notes", part, 0.35, 2.05, 12.6, size=18, wrapped=False)
    pending = []
    for interval in leg.coordination_rows:
        _, remaining, posture = _row_text(interval)
        # Expanded row cards hold complete causes/source identities at body
        # size. The table retains exact IDs/times and the immediate impact.
        facts = [f"Window {interval.window_number}", interval.id]
        facts += [
            f"{name}: {d.value}"
            for name, d in zip(TRANSPORT_NAMES, interval.decisions)
            if d.value != "Up"
        ]
        facts += [r.label for r in interval.restrictions]
        facts += list(
            dict.fromkeys(
                re.split(r"(?<=[.!?])\s+", cause)[0]
                for cause in (*interval.causes, *interval.limitations)
                if cause not in {r.label for r in interval.restrictions}
            )
        )
        facts = "\n".join(facts)
        values = (
            format_clocks(interval.start_time, leg.utc_bounds[0]).et.replace(
                " ", "\n", 1
            ),
            format_clocks(interval.end_time, leg.utc_bounds[0]).et.replace(
                " ", "\n", 1
            ),
            facts,
            remaining,
            posture,
        )
        # Oversize customer reasons continue with original IDs/endpoints,
        # never creating an additional semantic window or source outage.
        wrapped = [
            wrap(value, width, 20 if col < 2 else 18)
            for col, (value, width) in enumerate(zip(values, COLUMN_WIDTHS))
        ]
        lines = wrapped[2].split("\n")
        first = True
        while lines:
            prefix = (
                ""
                if first
                else wrap(
                    f"Window {interval.window_number}\n{interval.id}\ncontinued",
                    COLUMN_WIDTHS[2],
                    18,
                )
                + "\n"
            )
            reserved = len(prefix.split("\n")) - 1 if prefix else 0
            capacity = (
                int((2.95 - 0.08 - 0.10 - 2 * 1.20 / 72) / line_height(18)) - reserved
            )
            if capacity < 1:
                raise ValueError("Window identity exceeds readable table capacity")
            cells = list(wrapped)
            cells[2] = prefix + "\n".join(lines[:capacity])
            lines = lines[capacity:]
            row_height = (
                max(
                    text_height(value, 20 if col < 2 else 18)
                    + (2 * 1.20 / 72 if col == 2 else 0)
                    for col, value in enumerate(cells)
                )
                + 0.10
            )
            pending.append((cells, row_height, interval.id))
            first = False
    page = 0
    while pending:
        page += 1
        batch = []
        height = 1.30
        while pending and height + pending[0][1] <= 4.25:
            row = pending.pop(0)
            batch.append(row)
            height += row[1]
        if not batch:
            raise ValueError(
                "Essential coordination row exceeds readable page capacity"
            )
        slide = _page(
            prs,
            captured,
            leg,
            n,
            total,
            "coordination-table",
            f"Event / coordination windows · page {page}"
            + (" · continued" if page > 1 else ""),
        )
        table_shape = slide.shapes.add_table(
            1 + len(batch),
            5,
            Inches(0.35),
            Inches(2.05),
            Inches(sum(COLUMN_WIDTHS)),
            Inches(height),
        )
        table_shape.name = "coordination-table"
        table = table_shape.table
        table.first_row = True
        table.horz_banding = False
        for column, width in zip(table.columns, COLUMN_WIDTHS):
            column.width = Inches(width)
        table.rows[0].height = Inches(1.30)
        for col, label in enumerate(COLUMNS):
            cell = table.cell(0, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(NEUTRAL)
            style_frame(
                cell.text_frame, wrap(label, COLUMN_WIDTHS[col], 18, True), 18, True
            )
        for row_index, (cells, row_height, _) in enumerate(batch, 1):
            table.rows[row_index].height = Inches(row_height)
            for col, value in enumerate(cells):
                cell = table.cell(row_index, col)
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(255, 255, 255)
                style_frame(cell.text_frame, value, 20 if col < 2 else 18)
                if col == 2:
                    paragraph = cell.text_frame.paragraphs[0]
                    paragraph.line_spacing = Pt(20 * 1.20)
                    for run in paragraph.runs:
                        run.font.size = Pt(20)


def _window_details(prs, captured, leg, n, total):
    for interval in leg.coordination_rows:
        facts, _, _ = _row_text(interval)
        # The first two lines are the window label and immutable identity,
        # already repeated at 20 points above every expanded row card.
        content = "\n".join(facts.split("\n")[2:])
        for part_index, part in enumerate(chunks(content, 12.6, 18, 3.05)):
            slide = _page(
                prs,
                captured,
                leg,
                n,
                total,
                "window-detail",
                "Window causes / source references"
                + (" · continued" if part_index else ""),
            )
            textbox(
                slide,
                f"window:{interval.id}",
                f"Window {interval.window_number} · {interval.id}",
                0.35,
                1.95,
                12.6,
                0.50,
                size=20,
                bold=True,
            )
            a, b = format_clocks(interval.start_time, leg.utc_bounds[0]), format_clocks(
                interval.end_time, leg.utc_bounds[0]
            )
            textbox(
                slide,
                "time:window-range",
                f"Start {a.et} · End {b.et}",
                0.35,
                2.45,
                12.6,
                0.50,
                size=20,
            )
            textbox(
                slide, "window-facts", part, 0.35, 2.98, 12.6, size=18, wrapped=False
            )
            support = next(sh for sh in slide.shapes if sh.name == "support:clocks")
            style_frame(
                support.text_frame,
                f"Window Zulu {a.zulu} → {b.zulu} · {a.relative} → {b.relative} · Planned departure basis",
                14,
            )


def _appendix(prs, captured, leg, n, total):
    for interval in leg.intervals:
        content = f"Window {interval.window_number} · {interval.id}\nStart: {_clocks(interval.start_time, leg)}\nEnd: {_clocks(interval.end_time, leg)}\n{interval.posture}\n"
        content += "\n".join(
            f"{name}: {decision.value} · rule {decision.rule_id}"
            for name, decision in zip(TRANSPORT_NAMES, interval.decisions)
        )
        content += "\nSources: " + ", ".join(interval.active_source_ids)
        for part_index, part in enumerate(chunks(content, 12.6, 14, 3.85)):
            slide = _page(
                prs,
                captured,
                leg,
                n,
                total,
                "appendix-window",
                "Reference · window clocks" + (" · continued" if part_index else ""),
            )
            textbox(slide, "reference", part, 0.35, 2.05, 12.6, size=14, wrapped=False)
    for source in leg.sources:
        header = f"Source: {source.source_id}\n{source.source_type} · {source.transport.value if source.transport else 'Coordination / advisory'}\n"
        content = header
        for label, stamp in (
            ("Original start", source.start_time),
            ("Original end", source.end_time),
            ("Original instant", source.timestamp),
        ):
            if stamp:
                content += f"{label}: {_clocks(stamp, leg)}\n"
        content += f"Reason: {source.reason}\nRevision: {source.source_revision}\nDigest: {source.source_digest}\n"
        if source.derived_identity:
            content += "Derived source identity\n"
        content += "Captured metadata: " + json.dumps(
            source.metadata, ensure_ascii=False, sort_keys=True
        )
        for part_index, part in enumerate(chunks(content, 12.6, 14, 3.80)):
            slide = _page(
                prs,
                captured,
                leg,
                n,
                total,
                "appendix-source",
                "Reference · unsplit source" + (" · continued" if part_index else ""),
            )
            if part_index:
                part = f"Source continued: {source.source_id}\n" + part
            textbox(slide, "source", part, 0.35, 2.05, 12.6, size=14, wrapped=False)
    # Captured normalized timeline and advisories are reference-only. Preserve
    # source state fields and minor transitions without promoting new windows.
    timeline = json.loads(captured.timeline_json) if captured.timeline_json else {}
    for collection in ("segments", "advisories", "coverage_events"):
        for record in timeline.get(collection, []):
            content = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2)
            for part_index, part in enumerate(chunks(content, 12.6, 14, 3.80)):
                slide = _page(
                    prs,
                    captured,
                    leg,
                    n,
                    total,
                    "appendix-state",
                    f"Reference · {collection}"
                    + (" · continued" if part_index else ""),
                )
                textbox(slide, "state", part, 0.35, 2.05, 12.6, size=14, wrapped=False)


def _validate_inputs(snapshot, legs, maps):
    ids = tuple(c.leg_id for c in snapshot.legs)
    if (
        not ids
        or len(set(ids)) != len(ids)
        or ids != tuple(l.leg_id for l in legs)
        or ids != tuple(m.leg_id for m in maps)
    ):
        raise ValueError(
            "Captured, projected and map legs must agree in order and identity"
        )
    for leg in legs:
        if not leg.utc_bounds:
            if leg.intervals or leg.coordination_rows:
                raise ValueError("Untimed leg contains timed windows")
            continue
        if (
            not leg.intervals
            or (leg.intervals[0].start_time, leg.intervals[-1].end_time)
            != leg.utc_bounds
        ):
            raise ValueError("Timeline does not cover the whole flight")
        if any(a.end_time != b.start_time for a, b in pairwise(leg.intervals)):
            raise ValueError("Timeline partition has gaps or overlaps")
        by_id = {i.id: i for i in leg.intervals}
        if len(by_id) != len(leg.intervals):
            raise ValueError("Duplicate interval identity")
        for interval in leg.intervals:
            if (
                interval.start_time >= interval.end_time
                or len(interval.decisions) != 3
                or interval.posture not in POSTURE_COLORS
            ):
                raise ValueError("Invalid trial interval")
        if any(by_id.get(row.id) != row for row in leg.coordination_rows):
            raise ValueError("Table windows differ from timeline partition")


def _validate_deck(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Invalid PowerPoint ZIP")
        for name in archive.namelist():
            if name.endswith(".rels") and b'TargetMode="External"' in archive.read(
                name
            ):
                raise ValueError("Trial assets must be embedded offline")
    prs = Presentation(io.BytesIO(data))
    if (
        not prs.slides
        or prs.slide_width != Inches(WIDTH)
        or prs.slide_height != Inches(HEIGHT)
    ):
        raise ValueError("Invalid PowerPoint canvas")
    for slide in prs.slides:
        for shape in slide.shapes:
            if (
                min(shape.left, shape.top) < 0
                or shape.left + shape.width > prs.slide_width + 5
                or shape.top + shape.height > prs.slide_height + 5
            ):
                raise ValueError(f"Shape outside slide: {shape.name}")
            frames = []
            minimum = (
                14
                if slide.name.startswith("appendix")
                or shape.name.startswith("support:")
                else 18
            )
            if shape.name.startswith(("time:", "window:")):
                minimum = 20
            if shape.has_text_frame:
                frames.append((shape.text_frame, minimum))
            if shape.has_table:
                for row_index, row in enumerate(shape.table.rows):
                    for column_index, cell in enumerate(row.cells):
                        frames.append(
                            (
                                cell.text_frame,
                                20 if row_index and column_index < 2 else 18,
                            )
                        )
            for frame, required in frames:
                for paragraph in frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text and (
                            run.font.size is None or run.font.size.pt < required
                        ):
                            raise ValueError(
                                "Serialized trial font violates the presentation contract"
                            )

    return data


def build_trial_pptx(
    snapshot: ExportSnapshot, legs: tuple[TrialLeg, ...], maps: tuple[LegMapResult, ...]
) -> bytes:
    """Return a complete validated deck; all failures are atomic trial errors."""
    try:
        _validate_inputs(snapshot, legs, maps)
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(WIDTH), Inches(HEIGHT)
        prs.core_properties.title = "Customer briefing — Trial"
        prs.core_properties.subject = f"Snapshot {snapshot.fingerprint}"
        prs.core_properties.author = "APO"
        for n, (captured, leg, result) in enumerate(zip(snapshot.legs, legs, maps), 1):
            if leg.utc_bounds:
                _timeline(prs, captured, leg, result, n, len(legs))
                _table(prs, captured, leg, result, n, len(legs))
                _window_details(prs, captured, leg, n, len(legs))
            else:
                slide = _page(
                    prs,
                    captured,
                    leg,
                    n,
                    len(legs),
                    "incomplete",
                    "Incomplete leg data",
                )
                textbox(
                    slide,
                    "missing",
                    "Flight bounds unavailable. Communications posture cannot be established.",
                    0.35,
                    2.10,
                    9.4,
                    size=18,
                )
                _map(slide, result, result.views[0] if result.views else None)
                for note in (*leg.notes, *result.warnings):
                    for part in chunks(note, 12.6, 18, 3.8):
                        extra = _page(
                            prs,
                            captured,
                            leg,
                            n,
                            len(legs),
                            "incomplete-notes",
                            "Incomplete leg data · continued",
                        )
                        textbox(
                            extra,
                            "missing",
                            part,
                            0.35,
                            2.05,
                            12.6,
                            size=18,
                            wrapped=False,
                        )
        # Reference follows all primary legs, avoiding appendix interruption.
        for n, (captured, leg) in enumerate(zip(snapshot.legs, legs), 1):
            _appendix(prs, captured, leg, n, len(legs))
        output = io.BytesIO()
        prs.save(output)
        return _validate_deck(output.getvalue())
    except TrialGenerationError:
        raise
    except Exception as exc:
        raise TrialGenerationError(
            "Customer briefing trial could not be generated"
        ) from exc
