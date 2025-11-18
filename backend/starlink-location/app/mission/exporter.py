"""Mission timeline export utilities.

Transforms `MissionTimeline` data into CSV, XLSX, and PDF deliverables with
parallel timestamp formats (UTC, Eastern, and T+ offsets) suitable for
customer-facing mission briefs.
"""

from __future__ import annotations

import io
import json
import matplotlib
matplotlib.use('Agg')  # Headless mode for Docker
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.lines import Line2D
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

from app.mission.models import (
    Mission,
    MissionTimeline,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportState,
)
from app.services.route_manager import RouteManager

EASTERN_TZ = ZoneInfo("America/New_York")
LIGHT_YELLOW = colors.Color(1.0, 1.0, 0.85)
LIGHT_RED = colors.Color(1.0, 0.85, 0.85)
TRANSPORT_DISPLAY = {
    Transport.X: "X-Band",
    Transport.KA: "HCX",
    Transport.KU: "StarShield",
}
STATE_COLUMNS = [
    TRANSPORT_DISPLAY[Transport.X],
    TRANSPORT_DISPLAY[Transport.KA],
    TRANSPORT_DISPLAY[Transport.KU],
]
LOGO_PATH = Path(__file__).with_name("assets").joinpath("logo.png")

# Global route manager instance (set by main.py)
_route_manager: Optional[RouteManager] = None


def set_route_manager(route_manager: RouteManager) -> None:
    """Set the route manager instance (called by main.py during startup)."""
    global _route_manager
    _route_manager = route_manager


def _load_logo_flowable() -> Image | None:
    """Return a scaled logo image if available."""
    if not LOGO_PATH.exists():
        return None
    try:
        logo = Image(str(LOGO_PATH))
    except OSError:
        return None
    max_width = 1.6 * inch
    max_height = 0.9 * inch
    logo._restrictSize(max_width, max_height)
    logo.hAlign = "RIGHT"
    return logo


class ExportGenerationError(RuntimeError):
    """Raised when timeline export generation fails."""


class TimelineExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"

    @classmethod
    def from_string(cls, raw: str) -> "TimelineExportFormat":
        """Parse user-supplied format strings case-insensitively."""
        value = (raw or "").strip().lower()
        try:
            return cls(value)
        except ValueError as exc:
            raise ExportGenerationError(f"Unsupported export format: {raw}") from exc


@dataclass(slots=True)
class ExportArtifact:
    """Container describing a generated export file."""

    content: bytes
    media_type: str
    extension: str


def _ensure_timezone(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _mission_start_timestamp(timeline: MissionTimeline) -> datetime:
    """Infer the mission's zero point for T+ offsets."""
    if timeline.segments:
        earliest = min(_ensure_timezone(seg.start_time) for seg in timeline.segments)
        return earliest
    return _ensure_timezone(timeline.created_at)


def _format_utc(dt: datetime) -> str:
    """Return UTC string without seconds (timezone suffix indicates Z)."""
    return _ensure_timezone(dt).strftime("%Y-%m-%d %H:%MZ")


def _format_eastern(dt: datetime) -> str:
    """Return Eastern time with timezone abbreviation (DST-aware)."""
    eastern = _ensure_timezone(dt).astimezone(EASTERN_TZ)
    return eastern.strftime("%Y-%m-%d %H:%M%Z")


def _format_offset(delta: timedelta) -> str:
    """Format timedelta as T+/-HH:MM."""
    total_minutes = int(delta.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"T{sign}{hours:02d}:{minutes:02d}"


def _serialize_transport_list(transports: Iterable[Transport]) -> str:
    labels: list[str] = []
    for transport in transports:
        if isinstance(transport, Transport):
            labels.append(TRANSPORT_DISPLAY.get(transport, transport.value))
        else:
            labels.append(str(transport))
    return ", ".join(labels)


def _is_x_ku_conflict_reason(reason: str | None) -> bool:
    if not reason:
        return False
    return reason.startswith("X-Ku Conflict")


def _segment_is_x_ku_warning(segment: TimelineSegment) -> bool:
    if segment.x_state != TransportState.DEGRADED:
        return False
    if any(
        transport != Transport.X
        for transport in segment.impacted_transports
    ):
        return False
    if not segment.reasons:
        return False
    return all(_is_x_ku_conflict_reason(reason) for reason in segment.reasons)


def _display_transport_state(
    state: TransportState,
    *,
    warning_override: bool = False,
) -> str:
    if warning_override and state == TransportState.DEGRADED:
        return "WARNING"
    return state.value.upper()


def _aar_block_rows(
    timeline: MissionTimeline,
    mission: Mission | None,
    mission_start: datetime,
) -> list[tuple[datetime, int, dict]]:
    blocks = timeline.statistics.get("_aar_blocks") if timeline.statistics else None
    if not blocks:
        return []
    rows: list[tuple[datetime, int, dict]] = []
    for block in blocks:
        start_raw = block.get("start")
        end_raw = block.get("end")
        if not (start_raw and end_raw):
            continue
        start_dt = _parse_iso_timestamp(start_raw)
        end_dt = _parse_iso_timestamp(end_raw)
        if end_dt <= start_dt:
            continue
        rows.append(
            (
                start_dt,
                0,
                _build_aar_record(
                    start_dt,
                    end_dt,
                    mission,
                    timeline,
                    mission_start,
                ),
            )
        )
    return rows


def _parse_iso_timestamp(raw: str) -> datetime:
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        dt = datetime.fromtimestamp(0, tz=timezone.utc)
    return _ensure_timezone(dt)


def _build_aar_record(
    start: datetime,
    end: datetime,
    mission: Mission | None,
    timeline: MissionTimeline,
    mission_start: datetime,
) -> dict:
    duration = max((end - start).total_seconds(), 0)
    segment = _segment_at_time(timeline, start)
    x_state = (
        _display_transport_state(segment.x_state)
        if segment
        else ""
    )
    ka_state = (
        _display_transport_state(segment.ka_state)
        if segment
        else ""
    )
    ku_state = (
        _display_transport_state(segment.ku_state)
        if segment
        else ""
    )
    return {
        "Segment #": "AAR",
        "Mission ID": mission.id if mission else timeline.mission_id,
        "Mission Name": mission.name if mission and mission.name else timeline.mission_id,
        "Status": "WARNING",
        "Start Time": _compose_time_block(start, mission_start),
        "End Time": _compose_time_block(end, mission_start),
        "Duration": _format_seconds_hms(duration),
        TRANSPORT_DISPLAY[Transport.X]: x_state,
        TRANSPORT_DISPLAY[Transport.KA]: ka_state,
        TRANSPORT_DISPLAY[Transport.KU]: ku_state,
        "Impacted Transports": "",
        "Reasons": "AAR",
        "Metadata": "",
    }


def _segment_at_time(
    timeline: MissionTimeline,
    timestamp: datetime,
) -> TimelineSegment | None:
    ts = _ensure_timezone(timestamp)
    for segment in timeline.segments:
        start = _ensure_timezone(segment.start_time)
        end = (
            _ensure_timezone(segment.end_time)
            if segment.end_time
            else datetime.max.replace(tzinfo=timezone.utc)
        )
        if start <= ts < end:
            return segment
    return timeline.segments[-1] if timeline.segments else None


def _generate_route_map(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
    """Generate a PNG image of the route map with segment status coloring.

    Args:
        timeline: The mission timeline with segments and timing data
        mission: The mission object containing route and POI information (optional)

    Returns:
        PNG image as bytes. Returns a placeholder image if mission/route is None.
    """
    if mission is None or not mission.route_id or not _route_manager:
        # Return placeholder if no mission or route manager
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No route data available', ha='center', va='center')
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Fetch route from manager
    route = _route_manager.get_route(mission.route_id)
    if route is None or not route.points:
        # Return placeholder if route not found
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No waypoint data available', ha='center', va='center')
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Extract waypoints from route points
    waypoints = []
    for pt in route.points:
        waypoints.append((pt.longitude, pt.latitude))

    if not waypoints:
        # No valid waypoints
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No waypoint coordinates available', ha='center', va='center')
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Extract waypoint coordinates
    points = route.points
    lats = [p.latitude for p in points]
    lons = [p.longitude for p in points]

    # Calculate map bounds with 10% margin
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat_range = max_lat - min_lat if max_lat != min_lat else 1.0
    lon_range = max_lon - min_lon if max_lon != min_lon else 1.0
    margin_lat = lat_range * 0.1
    margin_lon = lon_range * 0.1

    bounds = {
        'north': max_lat + margin_lat,
        'south': min_lat - margin_lat,
        'east': max_lon + margin_lon,
        'west': min_lon - margin_lon,
    }

    # Create figure with cartopy
    fig = plt.figure(figsize=(12, 8), dpi=150)
    ax = fig.add_subplot(111, projection=ccrs.PlateCarree())

    # Set map extent
    ax.set_extent([bounds['west'], bounds['east'], bounds['south'], bounds['north']],
                  crs=ccrs.PlateCarree())

    # Add map features
    ax.coastlines(resolution='50m', linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAND, facecolor='lightgray', alpha=0.3)
    ax.add_feature(cfeature.OCEAN, facecolor='lightblue', alpha=0.2)
    ax.gridlines(draw_labels=True, alpha=0.3)

    # Map segment status to colors
    status_colors = {
        "NOMINAL": "#00FF00",     # Green
        "DEGRADED": "#FFFF00",    # Yellow
        "CRITICAL": "#FF0000",    # Red
    }

    # Distribute segments across waypoints proportionally by duration
    if timeline.segments:
        total_duration = sum(
            (_ensure_timezone(seg.end_time) - _ensure_timezone(seg.start_time)).total_seconds()
            for seg in timeline.segments
        )

        segment_idx = 0
        segment_progress = 0.0

        # Draw route segments colored by status
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            # Determine which segment(s) this route segment covers
            while segment_idx < len(timeline.segments):
                segment = timeline.segments[segment_idx]
                segment_duration = (
                    _ensure_timezone(segment.end_time) - _ensure_timezone(segment.start_time)
                ).total_seconds()
                segment_fraction = segment_duration / total_duration if total_duration > 0 else 0

                # Get segment status
                status_str = segment.status.value.upper() if hasattr(segment.status, 'value') else str(segment.status).upper()
                color = status_colors.get(status_str, "#808080")  # Gray as fallback

                # Draw line segment
                ax.plot([p1.longitude, p2.longitude],
                       [p1.latitude, p2.latitude],
                       color=color, linewidth=2, transform=ccrs.PlateCarree(),
                       zorder=3)

                segment_progress += segment_fraction
                if segment_progress >= 1.0 / (len(points) - 1):
                    segment_progress = 0.0
                    segment_idx += 1
                else:
                    break
    else:
        # If no timeline segments, draw route in gray
        ax.plot(lons, lats, color='#808080', linewidth=2,
               transform=ccrs.PlateCarree(), zorder=3)

    # Add departure marker (blue triangle at first waypoint)
    if points:
        first = points[0]
        ax.plot(first.longitude, first.latitude, marker='^', color='blue',
               markersize=12, transform=ccrs.PlateCarree(), zorder=4)

    # Add arrival marker (purple triangle at last waypoint)
    if points:
        last = points[-1]
        ax.plot(last.longitude, last.latitude, marker='^', color='purple',
               markersize=12, transform=ccrs.PlateCarree(), zorder=4)

    # Add mission-event POIs (orange circles with labels)
    if hasattr(mission, 'pois') and mission.pois:
        for poi in mission.pois:
            # Check if this is a mission-event POI
            poi_type = getattr(poi, 'category', None) or getattr(poi, 'poi_type', None)
            if poi_type == "mission-event":
                ax.plot(poi.longitude, poi.latitude, marker='o', color='orange',
                       markersize=8, transform=ccrs.PlateCarree(), zorder=4)
                # Add label
                ax.text(poi.longitude, poi.latitude, f"  {poi.name}",
                       fontsize=8, transform=ccrs.PlateCarree(), zorder=4)

    # Create legend
    legend_elements = [
        Line2D([0], [0], color='#00FF00', lw=2, label='Nominal'),
        Line2D([0], [0], color='#FFFF00', lw=2, label='Degraded'),
        Line2D([0], [0], color='#FF0000', lw=2, label='Critical'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='blue',
               markersize=8, label='Departure'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='purple',
               markersize=8, label='Arrival'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='orange',
               markersize=8, label='Mission Event'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9)

    # Add title
    mission_name = mission.name if hasattr(mission, 'name') else 'Mission'
    ax.set_title(f'Route Map: {mission_name}', fontsize=14, fontweight='bold')

    # Save to buffer
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def _generate_timeline_chart(timeline: MissionTimeline) -> bytes:
    """Generate a PNG image of a horizontal bar chart showing transport timeline.

    Args:
        timeline: The mission timeline with segments containing transport states

    Returns:
        PNG image as bytes showing three rows of colored blocks representing
        X-Band, Ka (HCX), and Ku (StarShield) state transitions over mission duration.
    """
    from matplotlib.ticker import FuncFormatter

    # Handle empty timeline
    if not timeline.segments:
        fig, ax = plt.subplots(figsize=(14, 4), dpi=150)
        ax.text(0.5, 0.5, 'No timeline segments available',
                ha='center', va='center', fontsize=14, transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()

    # Get mission duration from last segment end time
    mission_end_seconds = (
        _ensure_timezone(timeline.segments[-1].end_time) -
        _ensure_timezone(timeline.segments[0].start_time)
    ).total_seconds()

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(14, 4), dpi=150)

    # State to color mapping
    state_colors = {
        'AVAILABLE': '#00FF00',
        'DEGRADED': '#FFFF00',
        'OFFLINE': '#FF0000',
    }

    # Transport configuration: (y_position, name, state_getter)
    transports = [
        (0, 'Ku (StarShield)', lambda seg: seg.ku_state),
        (1, 'Ka (HCX)', lambda seg: seg.ka_state),
        (2, 'X-Band', lambda seg: seg.x_state),
    ]

    mission_start = _ensure_timezone(timeline.segments[0].start_time)

    # Draw segments for each transport
    for y_pos, transport_name, state_getter in transports:
        for segment in timeline.segments:
            seg_start = _ensure_timezone(segment.start_time)
            seg_end = _ensure_timezone(segment.end_time)

            # Calculate position and width in mission seconds
            start_offset = (seg_start - mission_start).total_seconds()
            duration = (seg_end - seg_start).total_seconds()

            # Get state and color
            state = state_getter(segment)
            state_str = state.value.upper() if hasattr(state, 'value') else str(state).upper()
            color = state_colors.get(state_str, '#808080')

            # Draw horizontal bar
            ax.barh(y_pos, duration, left=start_offset, height=0.8,
                   color=color, edgecolor='black', linewidth=0.5)

        # Label transport row
        ax.text(-50, y_pos, transport_name, ha='right', va='center', fontsize=10)

    # Configure y-axis
    ax.set_ylim(-0.5, 2.5)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(['Ku (StarShield)', 'Ka (HCX)', 'X-Band'])

    # Configure x-axis with T+ formatting
    def format_time_label(seconds, pos):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f'T+{hours:02d}:{minutes:02d}'

    ax.xaxis.set_major_formatter(FuncFormatter(format_time_label))
    ax.set_xlim(0, mission_end_seconds)

    # Add vertical grid lines at 1-hour intervals
    for hour in range(0, int(mission_end_seconds) + 1, 3600):
        if hour <= mission_end_seconds:
            ax.axvline(x=hour, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)

    # Configure grid and labels
    ax.grid(True, axis='x', alpha=0.3, linestyle='--')
    ax.set_xlabel('Mission Time', fontsize=11, fontweight='bold')
    ax.set_title('Transport State Timeline', fontsize=12, fontweight='bold')

    # Add legend
    legend_elements = [
        Line2D([0], [0], color='#00FF00', lw=10, label='Available'),
        Line2D([0], [0], color='#FFFF00', lw=10, label='Degraded'),
        Line2D([0], [0], color='#FF0000', lw=10, label='Offline'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

    # Adjust layout
    plt.tight_layout()

    # Save to buffer
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def _segment_rows(
    timeline: MissionTimeline,
    mission: Mission | None,
) -> pd.DataFrame:
    """Convert timeline segments into a pandas DataFrame."""
    mission_start = _mission_start_timestamp(timeline)
    rows: list[tuple[datetime, int, dict]] = []

    for idx, segment in enumerate(timeline.segments, start=1):
        start_utc = _ensure_timezone(segment.start_time)
        end_value = segment.end_time if segment.end_time else segment.start_time
        end_utc = _ensure_timezone(end_value)
        duration_seconds = max((end_utc - start_utc).total_seconds(), 0)
        warning_only = _segment_is_x_ku_warning(segment)
        status_value = (
            segment.status.value if isinstance(segment.status, TimelineStatus) else str(segment.status)
        )
        status_value = status_value.upper()
        impacted_display = _serialize_transport_list(segment.impacted_transports)
        if warning_only:
            status_value = TimelineStatus.NOMINAL.value.upper()
            impacted_display = ""
        record = {
            "Segment #": idx,
            "Mission ID": mission.id if mission else timeline.mission_id,
            "Mission Name": mission.name if mission and mission.name else timeline.mission_id,
            "Status": status_value,
            "Start Time": _compose_time_block(start_utc, mission_start),
            "End Time": _compose_time_block(end_utc, mission_start),
            "Duration": _format_seconds_hms(duration_seconds),
            TRANSPORT_DISPLAY[Transport.X]: _display_transport_state(
                segment.x_state, warning_override=warning_only
            ),
            TRANSPORT_DISPLAY[Transport.KA]: segment.ka_state.value.upper(),
            TRANSPORT_DISPLAY[Transport.KU]: segment.ku_state.value.upper(),
            "Impacted Transports": impacted_display,
            "Reasons": ", ".join(segment.reasons),
            "Metadata": json.dumps(segment.metadata, sort_keys=True) if segment.metadata else "",
        }
        rows.append((start_utc, 1, record))

    rows.extend(_aar_block_rows(timeline, mission, mission_start))

    columns = [
        "Segment #",
        "Mission ID",
        "Mission Name",
        "Status",
        "Start Time",
        "End Time",
        "Duration",
        TRANSPORT_DISPLAY[Transport.X],
        TRANSPORT_DISPLAY[Transport.KA],
        TRANSPORT_DISPLAY[Transport.KU],
        "Impacted Transports",
        "Reasons",
        "Metadata",
    ]

    ordered_records = [row for _, _, row in sorted(rows, key=lambda item: (item[0], item[1]))]
    return pd.DataFrame.from_records(ordered_records, columns=columns)


def _advisory_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame:
    """Convert timeline advisories into a pandas DataFrame (may be empty)."""
    mission_start = _mission_start_timestamp(timeline)
    records: list[dict] = []
    for advisory in timeline.advisories:
        ts_utc = _ensure_timezone(advisory.timestamp)
        records.append({
            "Mission ID": mission.id if mission else timeline.mission_id,
            "Timestamp (UTC)": _format_utc(ts_utc),
            "Timestamp (Eastern)": _format_eastern(ts_utc),
            "T Offset": _format_offset(ts_utc - mission_start),
            "Transport": advisory.transport.value if isinstance(advisory.transport, Transport) else advisory.transport,
            "Severity": advisory.severity,
            "Event Type": advisory.event_type,
            "Message": advisory.message,
            "Metadata": json.dumps(advisory.metadata, sort_keys=True) if advisory.metadata else "",
        })
    columns = [
        "Mission ID",
        "Timestamp (UTC)",
        "Timestamp (Eastern)",
        "T Offset",
        "Transport",
        "Severity",
        "Event Type",
        "Message",
        "Metadata",
    ]
    return pd.DataFrame.from_records(records, columns=columns)


def _statistics_rows(timeline: MissionTimeline) -> pd.DataFrame:
    stats = timeline.statistics or {}
    if not stats:
        return pd.DataFrame(columns=["Metric", "Value"])
    rows = []
    for key, value in stats.items():
        if key.startswith("_"):
            continue
        display_name = _humanize_metric_name(key)
        display_value = value
        if isinstance(value, (int, float)) and key.endswith("seconds"):
            display_value = _format_seconds_hms(value)
        rows.append({"Metric": display_name, "Value": display_value})
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def _format_seconds_hms(value: float | int) -> str:
    total_seconds = int(round(value))
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def _humanize_metric_name(key: str) -> str:
    label = key.replace("_", " ").strip()
    if key.endswith("seconds"):
        label = label[: -len("seconds")].strip()
        if not label.lower().endswith("duration"):
            label = f"{label} duration"
    label = label.title()
    return label or key


def _compose_time_block(moment: datetime, mission_start: datetime) -> str:
    utc = _format_utc(moment)
    eastern = _format_eastern(moment)
    offset = _format_offset(moment - mission_start)
    return f"{utc}\n{eastern}\n{offset}"


def generate_csv_export(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
    """Return CSV bytes for the mission timeline."""
    csv_buffer = io.StringIO()
    df = _segment_rows(timeline, mission)
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode("utf-8")


def _summary_table_rows(timeline: MissionTimeline, mission: Mission | None = None) -> pd.DataFrame:
    """Generate simplified summary table DataFrame with key columns for Sheet 1.

    Returns a DataFrame with columns: Start (UTC), Duration, Status, Systems Down
    """
    mission_start = _mission_start_timestamp(timeline)
    records: list[dict] = []

    for segment in timeline.segments:
        start_utc = _ensure_timezone(segment.start_time)
        end_value = segment.end_time if segment.end_time else segment.start_time
        end_utc = _ensure_timezone(end_value)
        duration_seconds = max((end_utc - start_utc).total_seconds(), 0)

        # Get segment status
        status_value = (
            segment.status.value if isinstance(segment.status, TimelineStatus) else str(segment.status)
        )
        status_value = status_value.upper()

        # Get systems down (impacted transports)
        systems_down = _serialize_transport_list(segment.impacted_transports)

        record = {
            "Start (UTC)": _format_utc(start_utc),
            "Duration": _format_seconds_hms(duration_seconds),
            "Status": status_value,
            "Systems Down": systems_down,
        }
        records.append(record)

    columns = ["Start (UTC)", "Duration", "Status", "Systems Down"]
    return pd.DataFrame.from_records(records, columns=columns)


def generate_xlsx_export(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
    """Return XLSX bytes containing Summary sheet (with map, chart, table) plus Timeline, Advisory, and Statistics sheets."""
    workbook_bytes = io.BytesIO()

    # Generate all data
    summary_df = _summary_table_rows(timeline, mission)
    timeline_df = _segment_rows(timeline, mission)
    advisories_df = _advisory_rows(timeline, mission)
    stats_df = _statistics_rows(timeline)
    map_image_bytes = _generate_route_map(timeline, mission)
    chart_image_bytes = _generate_timeline_chart(timeline)

    # Write DataFrames to Excel sheets
    with pd.ExcelWriter(workbook_bytes, engine="openpyxl") as writer:
        # Write Summary sheet first (will reorder later)
        summary_df.to_excel(writer, sheet_name="Summary", index=False, startrow=0)
        timeline_df.to_excel(writer, sheet_name="Timeline", index=False)
        if not advisories_df.empty:
            advisories_df.to_excel(writer, sheet_name="Advisories", index=False)
        if not stats_df.empty:
            stats_df.to_excel(writer, sheet_name="Statistics", index=False)

        # Access openpyxl workbook for image embedding and formatting
        wb = writer.book
        ws_summary = writer.sheets["Summary"]

        # Set column widths for summary sheet
        ws_summary.column_dimensions['A'].width = 25
        ws_summary.column_dimensions['B'].width = 15
        ws_summary.column_dimensions['C'].width = 12
        ws_summary.column_dimensions['D'].width = 30

        # Insert rows at top to accommodate map and chart images
        # Map will be at A1 (approximately 30 rows tall)
        # Chart will be at A32 (approximately 15 rows tall)
        # Table will be at A49
        ws_summary.insert_rows(1, 48)

        # Embed map image at A1
        try:
            map_image_stream = io.BytesIO(map_image_bytes)
            map_image = OpenpyxlImage(map_image_stream)
            map_image.width = 750  # pixels
            map_image.height = 500  # pixels
            ws_summary.add_image(map_image, 'A1')
        except Exception as e:
            # Log error but continue
            pass

        # Embed timeline chart at A32
        try:
            chart_image_stream = io.BytesIO(chart_image_bytes)
            chart_image = OpenpyxlImage(chart_image_stream)
            chart_image.width = 850  # pixels
            chart_image.height = 300  # pixels
            ws_summary.add_image(chart_image, 'A32')
        except Exception as e:
            # Log error but continue
            pass

        # Apply color formatting to summary table rows (starting at row 49)
        # Header is at row 49, data starts at row 50
        color_map = {
            "NOMINAL": PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid"),
            "DEGRADED": PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid"),
            "CRITICAL": PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
        }

        # Apply color to data rows (skip header row)
        for row_idx, (_, row) in enumerate(summary_df.iterrows(), start=50):
            status = row["Status"]
            fill = color_map.get(status)
            if fill:
                # Apply fill to columns A-D for this row
                for col_idx in range(1, 5):  # Columns A-D (1-4)
                    ws_summary.cell(row=row_idx, column=col_idx).fill = fill

    workbook_bytes.seek(0)
    wb_final = openpyxl.load_workbook(workbook_bytes)

    # Reorder sheets: move Summary to position 0 (first)
    if 'Summary' in wb_final.sheetnames:
        summary_sheet = wb_final['Summary']
        wb_final._sheets.remove(summary_sheet)
        wb_final._sheets.insert(0, summary_sheet)

    # Write final workbook to bytes
    final_bytes = io.BytesIO()
    wb_final.save(final_bytes)
    final_bytes.seek(0)
    return final_bytes.read()


def generate_pdf_export(timeline: MissionTimeline, mission: Mission | None = None) -> bytes:
    """Render a PDF brief summarizing the mission timeline."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(LETTER),
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story: list = []

    mission_name = mission.name if mission and mission.name else timeline.mission_id
    logo_flow = _load_logo_flowable()
    if logo_flow:
        logo_width = logo_flow.drawWidth
        header_table = Table(
            [
                [Paragraph("Mission Communication Timeline", styles["Title"]), logo_flow],
                [Paragraph(f"Mission: {mission_name}", styles["Heading2"]), Spacer(1, 0)],
            ],
            colWidths=[doc.width - logo_width, logo_width],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("SPAN", (1, 1), (1, 1)),
                ]
            )
        )
        story.append(header_table)
    else:
        story.append(Paragraph("Mission Communication Timeline", styles["Title"]))
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph(f"Mission: {mission_name}", styles["Heading2"]))
    story.append(Spacer(1, 0.2 * inch))

    stats_df = _statistics_rows(timeline)
    if not stats_df.empty:
        stats_table = Table(
            [["Metric", "Value"], *stats_df.values.tolist()],
            hAlign="LEFT",
        )
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ]
            )
        )
        story.append(stats_table)
        story.append(Spacer(1, 0.2 * inch))

    story.append(Spacer(1, 0.3 * inch))

    # Add route map
    story.append(Paragraph("Route Map", styles["Heading2"]))
    try:
        route_map_bytes = _generate_route_map(timeline, mission)
        route_map_stream = io.BytesIO(route_map_bytes)
        route_map_image = Image(route_map_stream, width=6.5 * inch, height=4.3 * inch)
        story.append(route_map_image)
    except Exception as e:
        story.append(Paragraph(f"[Route map unavailable: {str(e)}]", styles["Normal"]))

    # Page break before timeline
    story.append(PageBreak())

    # Add timeline chart
    story.append(Paragraph("Transport Timeline", styles["Heading2"]))
    try:
        chart_image_bytes = _generate_timeline_chart(timeline)
        chart_image_stream = io.BytesIO(chart_image_bytes)
        chart_image = Image(chart_image_stream, width=7 * inch, height=2.3 * inch)
        story.append(chart_image)
    except Exception as e:
        story.append(Paragraph(f"[Timeline chart unavailable: {str(e)}]", styles["Normal"]))

    story.append(Spacer(1, 0.2 * inch))

    timeline_df = _segment_rows(timeline, mission)
    if timeline_df.empty:
        story.append(Paragraph("No timeline segments were generated.", styles["Normal"]))
    else:
        story.append(Paragraph("Timeline Segments", styles["Heading2"]))
        table_columns = [
            ("", "Segment #"),
            ("Status", "Status"),
            ("Start Time", "Start Time"),
            ("End Time", "End Time"),
            ("Duration", "Duration"),
            (TRANSPORT_DISPLAY[Transport.X], TRANSPORT_DISPLAY[Transport.X]),
            (TRANSPORT_DISPLAY[Transport.KA], TRANSPORT_DISPLAY[Transport.KA]),
            (TRANSPORT_DISPLAY[Transport.KU], TRANSPORT_DISPLAY[Transport.KU]),
            ("Reasons", "Reasons"),
        ]
        body_style = styles["BodyText"]
        body_style.fontSize = 8
        body_style.leading = 9.5
        data = [[header for header, _ in table_columns]]
        for _, row in timeline_df.iterrows():
            row_values = []
            for header, key in table_columns:
                value = row[key]
                if key in {"Start Time", "End Time"}:
                    display = (value or "-").replace("\n", "<br/>")
                    row_values.append(Paragraph(display, body_style))
                elif key == "Reasons":
                    display = value or "-"
                    row_values.append(Paragraph(str(display), body_style))
                else:
                    row_values.append(value)
            data.append(row_values)

        column_weights = [0.5, 1.1, 1.5, 1.5, 0.8, 1.2, 1.2, 1.2, 3.0]
        width_unit = doc.width / sum(column_weights)
        col_widths = [weight * width_unit for weight in column_weights]
        table = Table(data, repeatRows=1, colWidths=col_widths)
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.4, 0.7)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ]
        column_index = {key: idx for idx, (_, key) in enumerate(table_columns)}
        state_column_indices = {name: column_index[name] for name in STATE_COLUMNS}
        for row_idx in range(len(timeline_df)):
            degraded_cols: list[int] = []
            for name in STATE_COLUMNS:
                column_idx = state_column_indices[name]
                cell_value = str(timeline_df.iloc[row_idx][name]).strip().lower()
                if cell_value in {"degraded", "offline"}:
                    degraded_cols.append(column_idx)
            if not degraded_cols:
                continue
            color = LIGHT_RED if len(degraded_cols) >= 2 else LIGHT_YELLOW
            for col_idx in degraded_cols:
                style_commands.append(
                    ("BACKGROUND", (col_idx, row_idx + 1), (col_idx, row_idx + 1), color)
                )
        table.setStyle(TableStyle(style_commands))
        story.append(table)

    footer_style = styles["Normal"].clone("Footer")
    footer_style.alignment = TA_RIGHT
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Timeline generated: {_format_utc(timeline.created_at)}", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generate_timeline_export(
    export_format: TimelineExportFormat,
    mission: Mission,
    timeline: MissionTimeline,
) -> ExportArtifact:
    """Generate the requested export artifact."""
    if export_format is TimelineExportFormat.CSV:
        content = generate_csv_export(timeline, mission)
        return ExportArtifact(content=content, media_type="text/csv", extension="csv")
    if export_format is TimelineExportFormat.XLSX:
        content = generate_xlsx_export(timeline, mission)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return ExportArtifact(content=content, media_type=media_type, extension="xlsx")
    if export_format is TimelineExportFormat.PDF:
        content = generate_pdf_export(timeline, mission)
        return ExportArtifact(content=content, media_type="application/pdf", extension="pdf")

    raise ExportGenerationError(f"Unsupported export format: {export_format}")
