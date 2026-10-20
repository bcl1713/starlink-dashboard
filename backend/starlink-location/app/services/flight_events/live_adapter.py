"""Bind accepted live observations to durable planned-leg identity."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.models.flight_status import FlightPhase
from app.services.flight_events.models import DetectionPolicy, FlightObservation
from app.services.flight_events.store import FlightEventStore
from app.services.kml.geometry import haversine_distance


class FlightEventRuntime:
    def __init__(self, root: Path):
        self.root = root
        self.events = FlightEventStore(root / "events.db")
        from app.services.telemetry_archive.coordinator import CaptureCoordinator
        from app.services.telemetry_archive.store import ArchiveStore

        self.archive = ArchiveStore(root / "archive.db")
        self.capture = CaptureCoordinator(self.events, self.archive)
        self.client = httpx.Client(
            base_url=os.getenv("STARLINK_PROMETHEUS_URL", "http://prometheus:9090"),
            timeout=3,
        )
        from app.mission.storage import load_mission_v2
        from app.services.telemetry_archive.preparation import (
            TelemetryPreparationService,
        )

        self.preparations = TelemetryPreparationService(
            root, self.archive, load_mission_v2
        )
        self.last_recovery = 0.0
        self.policy = DetectionPolicy.model_validate_json(
            os.getenv("FLIGHT_DETECTION_POLICY", "{}")
        )

    def changed(self, mission_id: str, leg_id: str) -> None:
        """Consume durable ledger notifications; acknowledgement follows commit."""
        self.capture.recover(datetime.now(timezone.utc))

    def accept(self, observation: FlightObservation):
        result = self.events.apply_observation(observation, self.policy)
        if result.emitted_events:
            self.capture.recover(observation.observed_at)
        return result

    def status(self, mission_id: str, leg_id: str) -> dict:
        state = self.events.state(mission_id, leg_id)
        events = self.events.events(mission_id, leg_id)
        result = {
            "movement_state": state.movement,
            "movement_uncertain": state.uncertain,
            "movement_observed_at": state.last_observed_at,
            "off_blocks_at": None,
            "takeoff_at": None,
            "landed_at": None,
            "on_blocks_at": None,
        }
        for event in events:
            field = {
                "off_blocks": "off_blocks_at",
                "takeoff": "takeoff_at",
                "landed": "landed_at",
                "on_blocks": "on_blocks_at",
            }.get(event.kind)
            if field and (field != "off_blocks_at" or result[field] is None):
                result[field] = event.occurred_at
        capture = self.archive.capture_summary(mission_id, leg_id)
        result["capture_state"] = capture["state"] if capture else "awaiting_off_blocks"
        return result

    def record_live(self, telemetry) -> None:
        """Persist accepted live observations even before a leg starts moving."""
        from app.services.position_freshness import (
            observation_time,
            position_observation,
            speed_is_fresh,
        )

        now = telemetry.timestamp
        position = telemetry.position
        fresh = (
            position_observation(
                position.latitude, position.longitude, position.observed_at, now
            )[1]
            == "fresh"
        )
        pairs = [
            (
                "starlink_dish_latitude_degrees",
                position.latitude if fresh else None,
                position.observed_at,
            ),
            (
                "starlink_dish_longitude_degrees",
                position.longitude if fresh else None,
                position.observed_at,
            ),
            (
                "starlink_dish_speed_knots",
                (
                    position.speed
                    if speed_is_fresh(position.speed, position.speed_observed_at, now)
                    else None
                ),
                position.speed_observed_at,
            ),
            (
                "starlink_dish_altitude_feet",
                (
                    position.altitude
                    if observation_time(position.altitude_observed_at, now)[1]
                    == "fresh"
                    else None
                ),
                position.altitude_observed_at,
            ),
        ]
        for field, metric in (
            ("latency_ms", "starlink_network_latency_ms_current"),
            ("throughput_down_mbps", "starlink_network_throughput_down_mbps_current"),
            ("throughput_up_mbps", "starlink_network_throughput_up_mbps_current"),
            ("packet_loss_percent", "starlink_network_packet_loss_percent"),
        ):
            pairs.append(
                (
                    metric,
                    (
                        getattr(telemetry.network, field)
                        if getattr(telemetry.metric_availability, field)
                        else None
                    ),
                    now,
                )
            )
        pairs.append(
            (
                "starlink_dish_obstruction_percent",
                (
                    telemetry.obstruction.obstruction_percent
                    if telemetry.metric_availability.obstruction_percent
                    else None
                ),
                now,
            )
        )
        self.archive.append_many(
            [
                (now, metric, {"source": "accepted_live"}, value, "live", observed)
                for metric, value, observed in pairs
            ]
        )

        from app.services.ground_entry_point import get_cached_ground_entry_point

        proxy = get_cached_ground_entry_point()
        if proxy is not None:
            labels = {
                "ip": proxy.ip,
                "city": proxy.city,
                "region": proxy.region,
                "country": proxy.country,
                "lat": proxy.latitude,
                "lon": proxy.longitude,
                "source": "cached_last_known_proxy",
            }
            self.archive.append_many(
                [
                    (now, metric, labels, 1, "live", None)
                    for metric in (
                        "starlink_ground_entry_point_info",
                        "starlink_ground_entry_point_location",
                    )
                ]
            )

    def tick(self, now: datetime | None = None) -> None:
        from app.services.telemetry_archive.reader import ArchiveReader

        now = now or datetime.now(timezone.utc)
        if time.monotonic() - self.last_recovery < 10:
            return
        self.last_recovery = time.monotonic()
        self.capture.recover(now)
        self.capture.backfill_one(ArchiveReader(self.client), now)
        self.archive.gc(now, self.events.earliest_pin())

    def close(self):
        self.client.close()
        self.preparations.close()

    def observe_live(self, telemetry, context, *, now: datetime | None = None):
        position = telemetry.position
        destination = context.route.points[-1] if context.route.points else None
        observation = FlightObservation(
            observed_at=position.observed_at or now or datetime.now(timezone.utc),
            received_at=now or datetime.now(timezone.utc),
            position_observed_at=position.observed_at,
            speed_observed_at=position.speed_observed_at,
            altitude_observed_at=position.altitude_observed_at,
            altitude_validity_source=position.altitude_validity_source,
            altitude_usable=position.altitude_observed_at is not None,
            latitude=position.latitude,
            longitude=position.longitude,
            speed_knots=position.speed,
            altitude_feet=position.altitude,
            source_mode="live",
            mission_id=context.parent_mission_id,
            leg_id=context.leg.id,
            route_id=context.route_id,
            destination_distance_m=(
                haversine_distance(
                    position.latitude,
                    position.longitude,
                    destination.latitude,
                    destination.longitude,
                )
                if destination
                else None
            ),
        )
        return self.accept(observation)

    def sync_legacy_phase(self, manager, mission_id: str, leg_id: str) -> None:
        status = self.status(mission_id, leg_id)
        movement = status["movement_state"]
        if movement in ("probable_landed_rollout", "taxi_in", "parked_at_stop") or (
            movement == "parked" and status["on_blocks_at"]
        ):
            target = FlightPhase.POST_ARRIVAL
            if manager.get_status().phase != target:
                manager.trigger_arrival(
                    status["landed_at"], "inferred live ground arrival"
                )
        elif movement == "airborne":
            if manager.get_status().phase != FlightPhase.IN_FLIGHT:
                manager.trigger_departure(
                    status["takeoff_at"], "inferred live departure"
                )
        elif movement in ("unknown", "taxi_out", "parked"):
            if manager.get_status().phase != FlightPhase.PRE_DEPARTURE:
                manager.transition_phase(
                    FlightPhase.PRE_DEPARTURE, "live detailed state"
                )
