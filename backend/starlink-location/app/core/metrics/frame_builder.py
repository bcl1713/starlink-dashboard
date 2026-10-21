"""Complete detached coupled-gauge preparation; no registry/producer commit."""

import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from math import isfinite, nan

from app.core import eta_service
from app.core.metrics import prometheus_metrics as metrics
from app.core.metrics.frames import FrameIdentity, GaugeFrame, PublicationState
from app.models.flight_status import ETAMode, FlightPhase, FlightStatus
from app.services.position_freshness import position_observation, speed_is_fresh


def _identity(value):
    if value is None:
        return None
    return sha256(value.model_dump_json().encode()).hexdigest()


@dataclass(frozen=True)
class FrameInputs:
    expected: PublicationState
    telemetry: object = None
    config: object = None
    active_route: object = None
    pois: tuple = ()
    flight_status: object = None
    mission_context: object = None
    progress: tuple | None = None  # (percent, waypoint index), supplied by producer
    replay_eta_metrics: dict | None = None
    now: datetime | None = None
    version: str | None = None

    def __post_init__(self):
        # No manager reference survives capture. Mutable domain models are detached.
        for name in (
            "telemetry",
            "config",
            "active_route",
            "flight_status",
            "mission_context",
            "progress",
            "replay_eta_metrics",
        ):
            value = getattr(self, name)
            if name == "config" and hasattr(value, "get_config"):
                value = value.get_config()
            object.__setattr__(self, name, deepcopy(value))
        object.__setattr__(self, "pois", tuple(deepcopy(poi) for poi in self.pois))
        object.__setattr__(self, "flight_status", self.flight_status or FlightStatus())
        object.__setattr__(self, "now", self.now or datetime.now(UTC))


def _prior(inputs, name, fallback=0):
    frame = inputs.expected.frame
    if frame is None:
        return fallback
    index = next(i for i, d in enumerate(metrics.COUPLED_SCHEMA) if d.name == name)
    samples = frame.families[index]
    return samples[0][1] if samples else fallback


def _mode(inputs):
    if inputs.mission_context is not None:
        return "replay"
    source = getattr(inputs.telemetry, "metric_source", None)
    if source in ("observed", "simulated"):
        return "live" if source == "observed" else "simulation"
    return getattr(
        inputs.config,
        "mode",
        inputs.expected.frame.identity.mode if inputs.expected.frame else "unknown",
    )


def prepare_frame(inputs: FrameInputs, admit_observation: bool) -> GaugeFrame:
    """Prepare all 29 families, without publishing or observing instruments."""
    telemetry, route, status = (
        inputs.telemetry,
        inputs.active_route,
        inputs.flight_status,
    )
    context = inputs.mission_context
    clock = context.simulation_time if context is not None else inputs.now
    phase, eta_mode = status.phase, status.eta_mode
    mode = _mode(inputs)
    identity = FrameIdentity(
        mode=mode,
        observation_id=telemetry.timestamp.isoformat() if telemetry else None,
        observation_timestamp=telemetry.timestamp.timestamp() if telemetry else None,
        route_id=_identity(route),
        poi_id=sha256(
            "".join(p.model_dump_json() for p in inputs.pois).encode()
        ).hexdigest(),
        phase_id=_identity(status),
        input_revision=inputs.expected.input_revision,
        replay_runtime_id=context.runtime_id if context else None,
        replay_run_id=context.run_id if context else None,
        replay_revision=str(context.revision) if context else None,
        replay_mission_time=clock.timestamp() if context else None,
    )
    previous_time = (
        inputs.expected.frame.last_observation_publication_time
        if inputs.expected.frame
        else 0.0
    )
    publication_time = (
        inputs.now.timestamp() if admit_observation and telemetry else previous_time
    )
    with metrics.FRAME_STORE.prepare(identity, publication_time) as builder:
        # Empty labelled families are intentional; unlabelled fields are always explicit.
        for definition in metrics.COUPLED_SCHEMA:
            if not definition.labelnames:
                builder.set(definition, (), nan)
        set_value = lambda name, value: getattr(metrics, name).set(value)
        position = telemetry.position if telemetry else None
        position_ready = (
            position is not None
            and position_observation(
                position.latitude, position.longitude, position.observed_at, inputs.now
            )[1]
            == "fresh"
        )
        # Legacy simulation and replay provide source-owned numeric speed; live
        # requires an explicit acquisition timestamp, including measured zero.
        speed_ready = position is not None and (
            (mode in ("simulation", "replay") and isfinite(position.speed))
            or speed_is_fresh(position.speed, position.speed_observed_at, inputs.now)
        )
        if position_ready:
            for field, name in (
                ("latitude", "latitude_degrees"),
                ("longitude", "longitude_degrees"),
                ("altitude", "altitude_feet"),
                ("heading", "heading_degrees"),
            ):
                set_value("starlink_dish_" + name, getattr(position, field))
            set_value(
                "starlink_dish_speed_knots", position.speed if speed_ready else nan
            )
        if telemetry:
            for source, field, gauge in (
                (
                    telemetry.network,
                    "latency_ms",
                    "starlink_network_latency_ms_current",
                ),
                (
                    telemetry.network,
                    "throughput_down_mbps",
                    "starlink_network_throughput_down_mbps_current",
                ),
                (
                    telemetry.network,
                    "throughput_up_mbps",
                    "starlink_network_throughput_up_mbps_current",
                ),
                (
                    telemetry.network,
                    "packet_loss_percent",
                    "starlink_network_packet_loss_percent",
                ),
                (
                    telemetry.obstruction,
                    "obstruction_percent",
                    "starlink_dish_obstruction_percent",
                ),
            ):
                set_value(
                    gauge,
                    (
                        getattr(source, field)
                        if getattr(
                            getattr(telemetry, "metric_availability", None),
                            field,
                            False,
                        )
                        else nan
                    ),
                )
            set_value(
                "starlink_signal_quality_percent",
                telemetry.environmental.signal_quality_percent,
            )
        set_value(
            "starlink_uptime_seconds",
            (
                telemetry.environmental.uptime_seconds
                if telemetry
                else _prior(inputs, "starlink_uptime_seconds")
            ),
        )
        set_value(
            "starlink_flight_phase",
            {"pre_departure": 0, "in_flight": 1, "post_arrival": 2}[phase.value],
        )
        set_value("starlink_eta_mode", 0 if eta_mode == ETAMode.ANTICIPATED else 1)
        set_value(
            "starlink_flight_departure_time_unix",
            status.departure_time.timestamp() if status.departure_time else 0,
        )
        set_value(
            "starlink_flight_arrival_time_unix",
            status.arrival_time.timestamp() if status.arrival_time else 0,
        )
        countdown = 0
        departure = status.departure_time
        if departure is None and route and route.timing_profile:
            departure = route.timing_profile.departure_time
        if departure is not None:
            departure = (
                departure.astimezone(UTC)
                if departure.tzinfo
                else departure.replace(tzinfo=UTC)
            )
            countdown = (departure - clock).total_seconds()
            if status.departure_time:
                countdown = max(0, countdown)
        set_value("starlink_time_until_departure_seconds", countdown)
        set_value("starlink_metrics_last_update_timestamp_seconds", publication_time)
        version = inputs.version
        if version is None and inputs.expected.frame:
            index = next(
                i
                for i, d in enumerate(metrics.COUPLED_SCHEMA)
                if d.name == "starlink_service_info"
            )
            samples = inputs.expected.frame.families[index]
            version = samples[0][0][0] if samples else None
        # Replay is a simulation source in the existing public mode contract.
        service_mode = "simulation" if mode == "replay" else mode
        metrics.starlink_service_info.labels(
            version=version or "0.2.0", mode=service_mode
        ).set(1)
        for label in ("simulation", "live"):
            metrics.starlink_mode_info.labels(mode=label).set(
                int(label == service_mode)
            )
        if route:
            labels = {"route_name": route.metadata.name}
            timing = route.timing_profile
            metrics.starlink_route_has_timing_data.labels(**labels).set(
                int(bool(timing and timing.has_timing_data))
            )
            for name, value in (
                (
                    "total_duration_seconds",
                    timing.total_expected_duration_seconds if timing else None,
                ),
                # Keep existing local-time mktime conversion; timezone cleanup is outside #391.
                (
                    "departure_time_unix",
                    (
                        time.mktime(timing.departure_time.timetuple())
                        if timing and timing.departure_time
                        else None
                    ),
                ),
                (
                    "arrival_time_unix",
                    (
                        time.mktime(timing.arrival_time.timetuple())
                        if timing and timing.arrival_time
                        else None
                    ),
                ),
                (
                    "segment_count_with_timing",
                    timing.segment_count_with_timing if timing else None,
                ),
            ):
                getattr(metrics, "starlink_route_" + name).labels(**labels).set(
                    value if value is not None else nan
                )
            if inputs.progress is not None:
                metrics.starlink_route_progress_percent.labels(**labels).set(
                    inputs.progress[0]
                )
                metrics.starlink_current_waypoint_index.labels(**labels).set(
                    inputs.progress[1]
                )
        preflight = phase == FlightPhase.PRE_DEPARTURE
        lat, lon = (
            (position.latitude, position.longitude) if position_ready else (nan, nan)
        )
        speed = position.speed if speed_ready and position_ready else None
        if preflight and (speed is None or speed < 0.5):
            speed = None  # 150 knots is an estimate, never an observed speed.
        elif not position_ready or not speed_ready:
            speed = None
        if inputs.replay_eta_metrics is not None:
            eta_values = inputs.replay_eta_metrics
        elif inputs.pois or (admit_observation and position_ready and speed_ready):
            eta_function = (
                eta_service._prepare_eta_metrics
                if admit_observation
                and position_ready
                and speed_ready
                and (preflight or speed >= 0.5)
                else eta_service.derive_eta_metrics
            )
            extra = (
                {"admit_observation": True}
                if eta_function is eta_service._prepare_eta_metrics
                else {}
            )
            eta_values = eta_function(
                lat,
                lon,
                speed,
                active_route=route,
                eta_mode=eta_mode,
                flight_phase=phase,
                pois=inputs.pois,
                **({"mission_now": clock} if context else {}),
                **extra
            )
        else:
            eta_values = {}
        for poi in inputs.pois:
            value = eta_values.get(poi.id, {})
            labels = {
                "name": poi.name,
                "category": poi.category or "",
                "eta_type": value.get("eta_type", eta_mode.value),
            }
            distance = value.get("distance_meters", nan) if position_ready else nan
            eta = value.get("eta_seconds", nan)
            if (
                eta is None
                or eta < 0
                or (
                    not preflight
                    and (
                        not position_ready
                        or not speed_ready
                        or speed is None
                        or speed < 0.5
                    )
                )
            ):
                eta = nan
            metrics.starlink_distance_to_poi_meters.labels(**labels).set(distance)
            metrics.starlink_eta_poi_seconds.labels(**labels).set(eta)
        return builder.seal()


def prepare_unavailable_frame(inputs: FrameInputs) -> GaugeFrame:
    """Retain only applicable planned/service fields and old observation time."""
    from dataclasses import replace

    return prepare_frame(replace(inputs, telemetry=None), admit_observation=False)
