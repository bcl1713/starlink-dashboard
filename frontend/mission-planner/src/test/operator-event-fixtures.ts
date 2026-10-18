import type { OperationalEvent, EventSnapshot } from '@/types/operatorEvents';
export function eventFixture(
  overrides: Partial<OperationalEvent> = {}
): OperationalEvent {
  return {
    schema_version: 1,
    event_id: 'event-a',
    mission_id: 'mission-a',
    leg_id: null,
    kind: 'call_start',
    title: 'Synthetic requirement',
    due_at: '2026-10-17T16:00:00Z',
    end_at: '2026-10-17T16:30:00Z',
    state: 'active',
    provenance: 'scheduled',
    source_ref: 'record-a',
    source_revision: '1',
    source_captured_at: '2026-10-17T15:00:00Z',
    freshness: 'fresh',
    confidence: null,
    transport: null,
    protected_participation_ids: [],
    conference_ids: [],
    transport_relevance: 'unknown',
    continuity_status: 'unknown',
    discrepancies: [],
    significance: 'routine',
    active: true,
    schedule_key: 'schedule-a',
    family_key: '',
    dependent_versions: { 'record-a': 1 },
    notification: {
      generation: 'occurrence-a',
      severity_generation: 2,
      acknowledged: false,
      acknowledged_at: null,
      retired: false,
      eligible: true,
      priority: 0,
      threshold_at: '2026-10-17T15:58:00Z',
      acknowledgment_available: true,
      available: true,
      reason: null,
    },
    ...overrides,
  };
}
export function eventSnapshot(
  overrides: Partial<EventSnapshot> = {}
): EventSnapshot {
  return {
    schema_version: 1,
    store_id: 'store',
    api_epoch: 'epoch-a',
    mission_id: 'mission-a',
    source_mode: 'live',
    simulation_run_id: null,
    as_of: '2026-10-17T16:00:00Z',
    H: 1,
    generation: 'snapshot-a',
    sources: [],
    coverage: 'partial',
    events: [eventFixture()],
    snapshot_token: 'snapshot-token',
    cursor: null,
    truncated: false,
    ...overrides,
  };
}
