#!/usr/bin/env python3
"""
Benchmark script for mission timeline recomputation performance.

Measures the time required to compute timelines for multiple concurrent missions
and validates that the system meets the <1.0s target for 10 concurrent missions.

Usage (in Docker):
    docker compose exec starlink-location python tools/benchmark_mission_timeline.py

Usage (pytest in Docker):
    docker compose exec starlink-location python -m pytest tests/performance/ -v
"""

import sys
import time
import psutil
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from app.mission.models import (
        Mission,
        Transport,
        TransportConfig,
        XTransition,
    )
    from app.mission.timeline_service import compute_mission_timeline
    from app.mission.storage import mission_exists, delete_mission
except ImportError as e:
    print(f"Error: Dependencies not available. This script must be run inside Docker.")
    print(f"Run: docker compose exec starlink-location python tools/benchmark_mission_timeline.py")
    print(f"ImportError: {e}")
    sys.exit(1)


def create_test_mission(mission_number: int) -> Mission:
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

    mission = Mission(
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


def benchmark_timeline_recompute(mission_count: int = 10, max_workers: int = 4) -> dict:
    """
    Measure timeline recompute time and memory for N concurrent missions.

    Args:
        mission_count: Number of missions to create and process
        max_workers: Maximum concurrent threads in executor

    Returns:
        Dictionary with benchmark results (time, memory, per-mission stats)
    """
    print(f"\n{'='*70}")
    print(f"Mission Timeline Performance Benchmark")
    print(f"{'='*70}")
    print(f"Missions to process: {mission_count}")
    print(f"Max concurrent workers: {max_workers}")
    print(f"Target time: < 1.0s for {mission_count} missions")
    print(f"{'='*70}\n")

    # Get process for memory tracking
    process = psutil.Process(os.getpid())

    # Create test missions
    print(f"[1/4] Creating {mission_count} test missions...")
    missions = [create_test_mission(i) for i in range(mission_count)]
    print(f"      ✓ Created {len(missions)} missions")

    # Measure memory before computation
    print(f"\n[2/4] Measuring baseline memory usage...")
    mem_before = process.memory_info().rss / 1024 / 1024  # Convert to MB
    print(f"      Baseline memory: {mem_before:.2f} MB")

    # Measure timeline recomputation
    print(f"\n[3/4] Computing timelines for {mission_count} missions (concurrent)...")
    start_time = time.time()

    results = []
    mission_times = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all missions to executor
        future_to_mission = {
            executor.submit(compute_mission_timeline, mission): mission
            for mission in missions
        }

        # Collect results as they complete
        completed = 0
        for future in as_completed(future_to_mission):
            mission = future_to_mission[future]
            try:
                timeline = future.result()
                results.append(timeline)
                mission_times[mission.id] = future._start_time if hasattr(future, '_start_time') else 0
                completed += 1
                # Show progress every 2 missions
                if completed % 2 == 0:
                    elapsed = time.time() - start_time
                    print(f"      Progress: {completed}/{mission_count} missions ({elapsed:.2f}s)")
            except Exception as e:
                print(f"      ✗ Error processing mission {mission.id}: {e}")

    total_duration = time.time() - start_time

    # Measure memory after computation
    mem_after = process.memory_info().rss / 1024 / 1024  # Convert to MB
    mem_delta = mem_after - mem_before

    # Calculate statistics
    avg_time_per_mission = total_duration / mission_count if mission_count > 0 else 0

    print(f"\n      ✓ Completed {len(results)} missions in {total_duration:.3f}s")

    # Measure memory and resources
    print(f"\n[4/4] Analyzing results...")
    print(f"      ✓ Memory before: {mem_before:.2f} MB")
    print(f"      ✓ Memory after:  {mem_after:.2f} MB")
    print(f"      ✓ Memory delta:  {mem_delta:+.2f} MB")

    print(f"\n{'='*70}")
    print(f"Benchmark Results")
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
        print(f"⚠️  Performance threshold exceeded by {total_duration - target_time:.3f}s")
        print(f"    Consider profiling hot paths or optimizing timeline computation\n")

    return {
        "mission_count": mission_count,
        "total_duration": total_duration,
        "avg_time_per_mission": avg_time_per_mission,
        "throughput": mission_count / total_duration,
        "memory_before_mb": mem_before,
        "memory_after_mb": mem_after,
        "memory_delta_mb": mem_delta,
        "successful_missions": len(results),
        "target_time": target_time,
        "passed": total_duration < target_time,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    try:
        # Run benchmark with 10 missions and 4 concurrent workers
        results = benchmark_timeline_recompute(mission_count=10, max_workers=4)

        # Exit with success code if target met
        exit_code = 0 if results["passed"] else 1
        sys.exit(exit_code)

    except Exception as e:
        print(f"\n✗ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
