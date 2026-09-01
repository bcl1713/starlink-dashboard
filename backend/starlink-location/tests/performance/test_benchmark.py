"""Performance benchmark tests for mission timeline recomputation.

This module provides benchmarks to measure the time required to compute timelines
for multiple concurrent missions and validates that the system meets the <1.0s
target for 10 concurrent missions.

Run with:
    pytest tests/performance/test_benchmark.py -v -s
"""

# FR-004: File exceeds 300 lines (334 lines) because the benchmark keeps setup,
# concurrent execution, persistence validation, and reporting in one scenario.

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psutil

from app.mission.models import (
    MissionLeg,
    TransportConfig,
    XTransition,
)
from app.mission.timeline_service import build_mission_timeline
from app.satellites.catalog import get_satellite_catalog
from app.satellites.coverage import CoverageSampler
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


def create_test_mission(mission_number: int) -> MissionLeg:
    """Create a test mission with realistic parameters for benchmarking."""
    unique_id = f"bench-mission-{uuid4().hex[:12]}"

    # Create mission with varying X transitions to simulate real workloads
    x_transitions = []
    if mission_number % 2 == 0:
        # Even missions: 2 X transitions
        x_transitions = [
            XTransition(
                id=f"transition-1-{unique_id}",
                latitude=40.0 + (mission_number * 0.5),
                longitude=-100.0 + (mission_number * 0.3),
                target_satellite_id="X-2" if mission_number % 3 == 0 else "X-1",
                target_beam_id=None,
                is_same_satellite_transition=False,
            ),
            XTransition(
                id=f"transition-2-{unique_id}",
                latitude=35.5 + (mission_number * 0.5),
                longitude=-87.0 + (mission_number * 0.3),
                target_satellite_id="X-1",
                target_beam_id=None,
                is_same_satellite_transition=False,
            ),
        ]

    mission = MissionLeg(
        id=unique_id,
        name=f"Benchmark Mission {mission_number}",
        description=f"Auto-generated mission for performance benchmarking (instance {mission_number})",
        route_id="test-route-cross-country",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=x_transitions,
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
        is_active=False,
    )
    return mission


def benchmark_timeline_recompute(
    mission_count: int = 10,
    max_workers: int = 10,
    pois_file: Path | None = None,
) -> dict:
    """
    Measure timeline recompute time and memory for N concurrent missions.

    Args:
        mission_count: Number of missions to create and process
        max_workers: Maximum concurrent threads in executor

    Returns:
        Dictionary with benchmark results (time, memory, per-mission stats)
    """
    print(f"\n{'='*70}")
    print("Mission Timeline Performance Benchmark")
    print(f"{'='*70}")
    print(f"Missions to process: {mission_count}")
    print(f"Max concurrent workers: {max_workers}")
    print(f"Target time: < 1.0s for {mission_count} missions")
    print(f"{'='*70}\n")

    # Get process for memory tracking
    process = psutil.Process(os.getpid())

    # Initialize managers needed for timeline computation
    print("[0/4] Initializing route and POI managers...")
    try:
        route_manager = RouteManager()
        poi_manager = POIManager(
            pois_file=pois_file or "/tmp/timeline-benchmark-pois.json"
        )

        # Create a test route if it doesn't exist
        from app.models.route import (
            ParsedRoute,
            RouteMetadata,
            RoutePoint,
            RouteTimingProfile,
        )

        test_route_id = "test-route-cross-country"
        if test_route_id not in route_manager._routes:
            # Create a simple test route with 10 waypoints
            points = [
                RoutePoint(
                    latitude=40.0 + i * 0.5,
                    longitude=-100.0 + i * 0.5,
                    altitude=10000.0,
                    sequence=i,
                )
                for i in range(10)
            ]
            metadata = RouteMetadata(
                name="Test Cross-Country Route",
                file_path="/tmp/test-route.kml",
                point_count=len(points),
                imported_at=datetime.now(timezone.utc),
            )
            # Create timing profile with departure/arrival times
            timing_profile = RouteTimingProfile(
                departure_time=datetime(2025, 11, 16, 10, 0, 0, tzinfo=timezone.utc),
                arrival_time=datetime(2025, 11, 16, 10, 5, 0, tzinfo=timezone.utc),
                flight_status="in_flight",
                has_timing_data=True,
            )
            test_route = ParsedRoute(
                metadata=metadata,
                points=points,
                waypoints=[],
                timing_profile=timing_profile,
            )
            route_manager._routes[test_route_id] = test_route

        print("      ✓ Managers initialized")
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:
        print(f"      ✗ Failed to initialize managers: {e}")
        raise

    # Create test missions
    print(f"\n[1/4] Creating {mission_count} test missions...")
    missions = [create_test_mission(i) for i in range(mission_count)]
    coverage_sampler = CoverageSampler()
    # Keep one-time catalog construction out of the measured durable mutation path.
    get_satellite_catalog()
    print(f"      ✓ Created {len(missions)} missions")

    # Measure memory before computation
    print("\n[2/4] Measuring baseline memory usage...")
    mem_before = process.memory_info().rss / 1024 / 1024  # Convert to MB
    print(f"      Baseline memory: {mem_before:.2f} MB")

    # Measure timeline recomputation
    print(f"\n[3/4] Computing timelines for {mission_count} missions (concurrent)...")
    start_time = time.time()

    results = []
    errors = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all missions to executor
        future_to_mission = {
            executor.submit(
                build_mission_timeline,
                mission,
                route_manager,
                poi_manager,
                coverage_sampler,
            ): mission
            for mission in missions
        }

        # Collect results as they complete
        completed = 0
        for future in as_completed(future_to_mission):
            mission = future_to_mission[future]
            try:
                timeline = future.result()
                results.append(timeline)
                completed += 1
                # Show progress every 2 missions
                if completed % 2 == 0:
                    elapsed = time.time() - start_time
                    print(
                        f"      Progress: {completed}/{mission_count} missions ({elapsed:.2f}s)"
                    )
            except (
                RuntimeError,
                ValueError,
                OSError,
                KeyError,
                TypeError,
                AttributeError,
                LookupError,
                ConnectionError,
                TimeoutError,
                ImportError,
                EOFError,
            ) as e:
                print(f"      ✗ Error processing mission {mission.id}: {e}")
                errors.append((mission.id, e))

    total_duration = time.time() - start_time

    # Measure memory after computation
    mem_after = process.memory_info().rss / 1024 / 1024  # Convert to MB
    mem_delta = mem_after - mem_before

    # Calculate statistics
    avg_time_per_mission = total_duration / mission_count if mission_count > 0 else 0

    if errors:
        error_summary = ", ".join(mission_id for mission_id, _ in errors)
        raise AssertionError(f"Benchmark mission failures: {error_summary}")

    reopened_poi_manager = POIManager(
        pois_file=pois_file or "/tmp/timeline-benchmark-pois.json"
    )
    persisted_mission_ids = {
        poi.mission_id
        for poi in reopened_poi_manager.list_pois()
        if poi.route_id == "test-route-cross-country"
    }
    expected_mission_ids = {mission.id for mission in missions}

    print(f"\n      ✓ Completed {len(results)} missions in {total_duration:.3f}s")

    # Measure memory and resources
    print("\n[4/4] Analyzing results...")
    print(f"      ✓ Memory before: {mem_before:.2f} MB")
    print(f"      ✓ Memory after:  {mem_after:.2f} MB")
    print(f"      ✓ Memory delta:  {mem_delta:+.2f} MB")

    print(f"\n{'='*70}")
    print("Benchmark Results")
    print(f"{'='*70}")
    print(f"Total missions:           {mission_count}")
    print(f"Concurrent workers:       {max_workers}")
    print(f"Total time:               {total_duration:.3f}s")
    print(f"Average per mission:      {avg_time_per_mission:.4f}s")
    print(f"Throughput:               {mission_count / total_duration:.1f} missions/s")
    print(f"Memory before:            {mem_before:.2f} MB")
    print(f"Memory after:             {mem_after:.2f} MB")
    print(f"Memory increase:          {mem_delta:+.2f} MB")
    print(f"{'='*70}\n")

    # Validate against target
    target_time = 1.0
    status = "✓ PASS" if total_duration < target_time else "✗ FAIL"
    print(f"Target: < {target_time:.1f}s for {mission_count} missions")
    print(f"Result: {total_duration:.3f}s")
    print(f"Status: {status}\n")

    if total_duration >= target_time:
        print(
            f"⚠️  Performance threshold exceeded by {total_duration - target_time:.3f}s"
        )
        print("    Consider profiling hot paths or optimizing timeline computation\n")

    return {
        "mission_count": mission_count,
        "total_duration": total_duration,
        "avg_time_per_mission": avg_time_per_mission,
        "throughput": mission_count / total_duration,
        "memory_before_mb": mem_before,
        "memory_after_mb": mem_after,
        "memory_delta_mb": mem_delta,
        "successful_missions": len(results),
        "persisted_mission_scopes": len(persisted_mission_ids),
        "expected_mission_scopes": len(expected_mission_ids),
        "all_mission_scopes_persisted": persisted_mission_ids == expected_mission_ids,
        "target_time": target_time,
        "passed": total_duration < target_time,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class TestTimelineBenchmark:
    """Benchmark test suite for mission timeline performance."""

    def test_10_concurrent_missions_under_budget(self):
        """Benchmark: 10 concurrent missions should complete under budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = benchmark_timeline_recompute(
                mission_count=10,
                max_workers=10,
                pois_file=Path(tmpdir) / "pois.json",
            )

        # Assert target is met
        assert results["passed"], (
            f"Benchmark failed: {results['total_duration']:.3f}s "
            f"exceeded target of {results['target_time']:.1f}s"
        )

        # Assert all missions were processed
        assert results["successful_missions"] == results["mission_count"], (
            f"Only {results['successful_missions']} of {results['mission_count']} "
            "missions completed successfully"
        )
        assert results["all_mission_scopes_persisted"], (
            f"Persisted {results['persisted_mission_scopes']} mission scopes, "
            f"expected {results['expected_mission_scopes']}"
        )
