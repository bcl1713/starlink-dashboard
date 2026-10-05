import type {
  SimulationPreview,
  SimulationRunStatus,
} from '@/services/simulation-run';

export const preview: SimulationPreview = {
  pacing: { mode: 'multiplier', multiplier: 10 },
  effective_multiplier: 10,
  flight_duration_seconds: 1200,
  expected_runtime_seconds: 120,
  plan_token: 'a'.repeat(64),
  planned_departure: '2025-01-01T01:00:00Z',
  planned_arrival: '2025-01-01T01:20:00Z',
  limits: { min_multiplier: 0.1, max_multiplier: 1000, min_runtime_seconds: 1 },
};
export function runningStatus(): SimulationRunStatus {
  return {
    runtime_id: 'runtime-1',
    revision: 2,
    service_mode: 'simulation',
    state: 'running',
    served_at: '2026-10-05T00:00:00Z',
    run: {
      pacing: preview.pacing,
      effective_multiplier: preview.effective_multiplier,
      flight_duration_seconds: preview.flight_duration_seconds,
      expected_runtime_seconds: preview.expected_runtime_seconds,
      plan_token: preview.plan_token,
      planned_departure: preview.planned_departure,
      planned_arrival: preview.planned_arrival,
      run_id: 'run-1',
      mission_id: 'mission-1',
      leg_id: 'leg-1',
      route_id: 'route-1',
      simulation_time: '2025-01-01T01:02:00Z',
      started_at: '2026-10-04T23:59:48Z',
      observed_at: '2026-10-05T00:00:00Z',
      finished_at: null,
      elapsed_real_seconds: 12,
      completion_lateness_seconds: null,
      progress_percent: 10,
      phase: 'in_flight',
      processed_event_count: 2,
      transport_states: { X: 'available', Ka: 'degraded', Ku: 'offline' },
      error: null,
    },
  };
}
export function completedStatus(): SimulationRunStatus {
  const status = runningStatus();
  return {
    ...status,
    state: 'completed',
    revision: 3,
    run: {
      ...status.run!,
      simulation_time: preview.planned_arrival,
      progress_percent: 100,
      phase: 'post_arrival',
      elapsed_real_seconds: 120,
      completion_lateness_seconds: 0,
      finished_at: '2026-10-05T00:01:48Z',
    },
  };
}
