"""Unit tests for mission timeline exporters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import app.mission.exporter as mission_exporter
from app.mission.exporter import (
    ExportGenerationError,
    TimelineExportFormat,
    generate_timeline_export,
)
from app.mission.exporter.__main__ import _compact_reason_label
from app.mission.models import (
    MissionLeg,
    MissionLegTimeline,
    TimelineAdvisory,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportConfig,
    TransportState,
)


def _build_test_mission() -> MissionLeg:
    return MissionLeg(
        id="mission-export-test",
        name="Export Test Mission",
        route_id="route-123",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[],
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
    )


def _build_test_timeline(mission_id: str) -> MissionLegTimeline:
    start = datetime(2025, 11, 5, 0, 0, tzinfo=timezone.utc)
    segments = [
        TimelineSegment(
            id="seg-1",
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=TimelineStatus.NOMINAL,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=[],
            impacted_transports=[],
            metadata={"note": "initial climb"},
        ),
        TimelineSegment(
            id="seg-2",
            start_time=start + timedelta(minutes=30),
            end_time=start + timedelta(hours=1),
            status=TimelineStatus.DEGRADED,
            x_state=TransportState.OFFLINE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=["x_azimuth_conflict"],
            impacted_transports=[Transport.X],
            metadata={"satellite_to": "X-2"},
        ),
    ]
    advisories = [
        TimelineAdvisory(
            id="adv-1",
            timestamp=start + timedelta(minutes=25),
            event_type="transition",
            transport=Transport.X,
            severity="warning",
            message="Disable X for transition to X-2.",
            metadata={"buffer_minutes": 15},
        )
    ]
    return MissionLegTimeline(
        mission_leg_id=mission_id,
        segments=segments,
        advisories=advisories,
        statistics={
            "total_duration_seconds": 3600,
            "nominal_seconds": 1800,
            "degraded_seconds": 1800,
            "critical_seconds": 0,
        },
    )


class TestTimelineExportFormat:
    def test_from_string_accepts_mixed_casing(self):
        assert TimelineExportFormat.from_string("CSV") is TimelineExportFormat.CSV
        assert TimelineExportFormat.from_string("Pptx") is TimelineExportFormat.PPTX

    def test_from_string_invalid_raises(self):
        with pytest.raises(ExportGenerationError):
            TimelineExportFormat.from_string("docx")


class TestMissionTimelineExporters:
    @pytest.fixture
    def mission(self) -> MissionLeg:
        return _build_test_mission()

    @pytest.fixture
    def timeline(self, mission: MissionLeg) -> MissionLegTimeline:
        return _build_test_timeline(mission.id)

    def test_generate_csv_contains_expected_headers(self, mission, timeline):
        output = generate_timeline_export(
            TimelineExportFormat.CSV, mission, timeline
        ).content.decode("utf-8")
        assert "Segment #" in output
        assert "Mission ID" in output
        assert timeline.mission_leg_id in output
        assert "X-Band" in output
        assert "CommKa" in output
        assert "StarShield" in output

    def test_generate_pptx_starts_with_zip_header(self, mission, timeline):
        output = generate_timeline_export(
            TimelineExportFormat.PPTX, mission, timeline
        ).content
        assert output.startswith(b"PK")

    def test_generate_timeline_export_router(self, mission, timeline):
        artifact = generate_timeline_export(TimelineExportFormat.CSV, mission, timeline)
        assert artifact.extension == "csv"
        assert artifact.media_type == "text/csv"

    def test_x_ku_conflict_segments_render_as_transport_concurrency_advisory(
        self, mission
    ):
        start = datetime(2025, 11, 5, 2, 0, tzinfo=timezone.utc)
        warning_segment = TimelineSegment(
            id="seg-warning",
            start_time=start,
            end_time=start + timedelta(minutes=10),
            status=TimelineStatus.DEGRADED,
            x_state=TransportState.DEGRADED,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=["X-Ku Conflict az=180° el=20°"],
            impacted_transports=[Transport.X],
            metadata={},
        )
        timeline = MissionLegTimeline(
            mission_leg_id=mission.id,
            segments=[warning_segment],
            advisories=[],
            statistics={},
        )

        df = mission_exporter._segment_rows(timeline, mission)
        row = df.iloc[0]
        assert row["Status"] == "ADVISORY"
        assert row["Call Posture"] == "Transport concurrency advisory"
        assert row["Primary Reason"] == "X Band / Ku conflict"
        assert row["X-Band"] == "AVAILABLE"
        assert row["StarShield"] == "AVAILABLE"
        assert row["Systems Affected"] == ""
        assert row["Reasons"] == "X/Ku Conflict"
        assert "PACE" not in row["Reasons"]

    def test_aar_boundary_and_landing_markers_export_inline_in_reasons(self, mission):
        start = datetime(2025, 11, 5, 18, 34, tzinfo=timezone.utc)
        segment = TimelineSegment(
            id="seg-x-ku-aar",
            start_time=start,
            end_time=start + timedelta(minutes=104),
            status=TimelineStatus.DEGRADED,
            x_state=TransportState.DEGRADED,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=["X Band / Ku conflict", "Safety-of-Flight (landing)"],
            impacted_transports=[Transport.X],
            metadata={},
        )
        timeline = MissionLegTimeline(
            mission_leg_id=mission.id,
            segments=[segment],
            advisories=[],
            statistics={
                "_aar_blocks": [
                    {
                        "start": (start + timedelta(minutes=8)).isoformat(),
                        "end": (start + timedelta(minutes=104)).isoformat(),
                    }
                ]
            },
        )

        df = mission_exporter._segment_rows(timeline, mission)

        assert "Operational Markers" not in df.columns
        aar_start = df[df["Start Time"].str.contains("18:42Z")].iloc[0]
        assert aar_start["Status"] == "ADVISORY"
        assert aar_start["Reasons"] == "AAR Start"

    def test_aar_block_rows_normalize_primary_table_without_overlap(self, mission):
        start = datetime(2025, 11, 5, 0, 0, tzinfo=timezone.utc)
        segments = [
            TimelineSegment(
                id="seg-1",
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status=TimelineStatus.NOMINAL,
                x_state=TransportState.AVAILABLE,
                ka_state=TransportState.AVAILABLE,
                ku_state=TransportState.AVAILABLE,
                reasons=[],
                impacted_transports=[],
                metadata={},
            )
        ]
        timeline = MissionLegTimeline(
            mission_leg_id=mission.id,
            segments=segments,
            advisories=[],
            statistics={
                "_aar_blocks": [
                    {
                        "start": start.isoformat(),
                        "end": (start + timedelta(minutes=10)).isoformat(),
                    }
                ]
            },
        )

        df = mission_exporter._segment_rows(timeline, mission)
        assert "AAR" not in df["Segment #"].values
        assert list(df["Status"]) == ["ADVISORY", "NOMINAL"]
        assert list(df["Call Posture"]) == [
            "Safety-of-flight advised",
            "Nominal calls",
        ]
        assert list(df["Primary Reason"]) == ["AAR window", "nominal window"]
        assert list(df["Reasons"]) == ["AAR Start", "AAR End"]
        assert df.iloc[0]["Systems Affected"] == ""

    def test_takeoff_landing_sof_reasons_use_compact_labels(self, mission):
        start = datetime(2025, 11, 5, 0, 0, tzinfo=timezone.utc)
        segments = [
            TimelineSegment(
                id="seg-takeoff",
                start_time=start,
                end_time=start + timedelta(minutes=15),
                status=TimelineStatus.SOF,
                x_state=TransportState.AVAILABLE,
                ka_state=TransportState.AVAILABLE,
                ku_state=TransportState.AVAILABLE,
                reasons=["Safety-of-Flight (takeoff)"],
                impacted_transports=[],
                metadata={},
            ),
            TimelineSegment(
                id="seg-landing",
                start_time=start + timedelta(minutes=30),
                end_time=start + timedelta(minutes=45),
                status=TimelineStatus.SOF,
                x_state=TransportState.AVAILABLE,
                ka_state=TransportState.AVAILABLE,
                ku_state=TransportState.AVAILABLE,
                reasons=["Safety-of-Flight (landing)"],
                impacted_transports=[],
                metadata={},
            ),
        ]
        timeline = MissionLegTimeline(
            mission_leg_id=mission.id,
            segments=segments,
            advisories=[],
            statistics={},
        )

        df = mission_exporter._segment_rows(timeline, mission)

        assert list(df["Reasons"]) == ["Takeoff", "Landing"]

    def test_satellite_swap_reason_uses_compact_transition_label(self, mission):
        start = datetime(2025, 11, 5, 4, 38, tzinfo=timezone.utc)
        segment = TimelineSegment(
            id="seg-ka-swap",
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=TimelineStatus.DEGRADED,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.DEGRADED,
            ku_state=TransportState.AVAILABLE,
            reasons=["Degraded — Satellite swap: Ka transition POR → AOR"],
            impacted_transports=[Transport.KA],
            metadata={},
        )
        timeline = MissionLegTimeline(
            mission_leg_id=mission.id,
            segments=[segment],
            advisories=[],
            statistics={},
        )

        df = mission_exporter._segment_rows(timeline, mission)

        assert df.iloc[0]["Reasons"] == "Ka POR => AOR"

    def test_aar_window_without_boundary_uses_compact_label(self, mission):
        start = datetime(2025, 11, 5, 0, 5, tzinfo=timezone.utc)
        segment = TimelineSegment(
            id="seg-aar-window",
            start_time=start,
            end_time=start + timedelta(minutes=10),
            status=TimelineStatus.SOF,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=["Safety-of-flight advised — AAR window"],
            impacted_transports=[],
            metadata={"operational_markers": ["AAR window"]},
        )

        assert _compact_reason_label(segment) == "AAR Window"

    def test_x_satellite_swap_reason_uses_compact_transition_label(self, mission):
        start = datetime(2025, 11, 5, 4, 38, tzinfo=timezone.utc)
        segment = TimelineSegment(
            id="seg-x-swap",
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=TimelineStatus.DEGRADED,
            x_state=TransportState.DEGRADED,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=["Degraded — Satellite swap: X Transition to X-6"],
            impacted_transports=[Transport.X],
            metadata={},
        )
        timeline = MissionLegTimeline(
            mission_leg_id=mission.id,
            segments=[segment],
            advisories=[],
            statistics={},
        )

        df = mission_exporter._segment_rows(timeline, mission)

        assert df.iloc[0]["Reasons"] == "X => X-6"
