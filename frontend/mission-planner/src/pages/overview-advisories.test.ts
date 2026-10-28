import { expect, it } from 'vitest';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
import type { EventSnapshot, OperationalEvent } from '@/types/operatorEvents';
import {
  deriveOverviewAdvisories,
  overviewAdvisoryContext,
} from './overview-advisories';

const now = Date.parse('2026-10-17T16:00:00Z');
const context = {
  missionId: 'mission-a',
  legId: 'leg-a',
  storeId: 'store',
  apiEpoch: 'epoch-a',
  sourceMode: 'live' as const,
  sourceIdentity: null,
  missionJournal: false,
  operatingContextId: null,
  replayRunId: null,
};
function event(overrides: Partial<OperationalEvent> = {}) {
  return eventFixture({
    kind: 'restriction',
    leg_id: 'leg-a',
    provenance: 'modeled',
    source_ref: 'model:leg-a',
    transport: 'Ka',
    significance: 'unavailable',
    title: 'KA Service Interruption Expected',
    ...overrides,
  });
}
function snapshot(events = [event()], overrides: Partial<EventSnapshot> = {}) {
  return eventSnapshot({
    events,
    coverage: 'available',
    sources: [
      {
        source: 'model:leg-a',
        revision: '1',
        generation: '1',
        input_identity: 'route',
        captured_at: '2026-10-17T16:00:00Z',
        freshness: 'fresh',
        aligned: true,
        guardable: true,
        reason: null,
      },
    ],
    ...overrides,
  });
}
function view(data = snapshot(), overrides = {}) {
  return deriveOverviewAdvisories({
    snapshot: data,
    context,
    missionNowMs: now,
    receivedAgeMs: 0,
    visible: true,
    failed: false,
    ...overrides,
  });
}

it('shows simultaneous KA, X and Starshield windows even when PoP is not audible eligible', () => {
  const pop = event({
    event_id: 'pop',
    kind: 'pop_advisory',
    advisory_type: 'transition_window',
    title: 'Starshield Transition Window',
    transport: 'Starshield',
    significance: 'advisory',
  });
  pop.notification = {
    ...pop.notification,
    eligible: false,
    threshold_at: pop.due_at,
  };
  const items = view(
    snapshot([
      event(),
      event({
        event_id: 'x',
        transport: 'X',
        title: 'X-Band Concurrency Restriction',
        significance: 'degraded',
        advisory_type: 'concurrency_restriction',
      }),
      pop,
    ])
  ).items;
  expect(items.map((i) => i.title)).toEqual([
    'KA Service Interruption Expected',
    'X-Band Concurrency Restriction',
    'Starshield Transition Window',
  ]);
  expect(items.at(-1)?.detail).toContain('Brief Interruption Possible');
});
it('uses backend threshold and end, with explicit approaching/model provenance', () => {
  const data = snapshot([event({ due_at: '2026-10-17T16:04:00Z' })]);
  data.events[0].notification.threshold_at = '2026-10-17T15:59:00Z';
  expect(view(data).items[0].detail).toContain('Approaching');
  expect(
    view(data, { missionNowMs: Date.parse('2026-10-17T15:58:59Z') }).items
  ).toHaveLength(0);
  expect(
    view(data, { missionNowMs: Date.parse('2026-10-17T16:30:00Z') }).items
  ).toHaveLength(0);
});
it.each(['acknowledged', 'retired', 'preview'] as const)(
  'suppresses %s without changing source/history',
  (field) => {
    const data = snapshot();
    data.events[0].notification[field] = true;
    const before = structuredClone(data);
    expect(view(data).items).toHaveLength(0);
    expect(data).toEqual(before);
  }
);
it('keeps PoP unknown/mismatch/unconfirmed diagnostics off Overview', () => {
  for (const advisory_type of [
    'observation_unknown',
    'observation_mismatch',
    'handover_unconfirmed',
  ] as const) {
    expect(
      view(
        snapshot([
          event({
            kind: 'pop_advisory',
            advisory_type,
            provenance: 'observed',
            significance: 'advisory',
          }),
        ])
      ).items
    ).toHaveLength(0);
  }
});
it.each([{ failed: true }, { context: null }, { receivedAgeMs: 45001 }])(
  'reports unavailable/stale rather than all clear %j',
  (overrides) => {
    expect(view(snapshot(), overrides)).toMatchObject({
      items: [],
      notice: expect.stringMatching(/Unavailable|Stale/),
    });
  }
);
it('uses wall receipt age even during replay and permits the bounded hidden poll interval', () => {
  expect(
    view(snapshot(), { visible: false, receivedAgeMs: 149999 }).items
  ).toHaveLength(1);
  expect(
    view(snapshot(), { visible: false, receivedAgeMs: 150001 }).notice
  ).toContain('Stale');
});
it.each([
  { store_id: 'other' },
  { api_epoch: 'other' },
  { mission_id: 'other' },
  { source_mode: 'simulation' as const },
  { simulation_run_id: 'old-run' },
  { truncated: true },
  { cursor: 'more' },
])('quarantines wrong or incomplete snapshots %j', (overrides) => {
  expect(view(snapshot(undefined, overrides))).toMatchObject({
    items: [],
    notice: 'Transport Advisories Unavailable',
  });
});
it('shows valid advisories with an unavailable notice when sources are partial, and hides misaligned/stale event sources', () => {
  const data = snapshot(undefined, { coverage: 'partial' });
  expect(view(data)).toMatchObject({
    items: [expect.any(Object)],
    notice: 'Transport Advisories Unavailable',
  });
  data.sources[0].aligned = false;
  expect(view(data).items).toHaveLength(0);
  data.sources[0].aligned = true;
  data.sources[0].freshness = 'stale';
  expect(view(data).items).toHaveLength(0);
});
it('never shows another leg or operating context, including late response after a switch', () => {
  expect(view(snapshot([event({ leg_id: 'leg-b' })])).items).toHaveLength(0);
  const journal = {
    ...context,
    missionJournal: true,
    sourceIdentity: 'ctx-a',
    operatingContextId: 'ctx-a',
    replayRunId: 'run-a',
  };
  const data = snapshot(
    [event({ operating_context_id: 'ctx-old', replay_run_id: 'run-a' })],
    { simulation_run_id: 'ctx-a' }
  );
  expect(view(data, { context: journal }).items).toHaveLength(0);
});
it('requires actual active mission/leg and aligned health identity', () => {
  const active = {
    state: 'available',
    mission_id: 'mission-a',
    leg_id: 'leg-a',
    mission_name: '',
    leg_name: '',
    phase: 'in_flight',
    source_mode: 'simulation' as const,
    replay_run_id: 'run-a',
    operating_context_id: 'ctx-a',
  };
  const health = {
    schema_version: 1 as const,
    enabled: true,
    ready: true,
    store_id: 'store',
    api_epoch: 'epoch-a',
    source_mode: 'simulation' as const,
    simulation_run_id: 'journal',
    clock_regression: false,
    error_code: null,
    mission_journal: true,
    operating_context_id: 'ctx-a',
    replay_run_id: 'run-a',
  };
  expect(overviewAdvisoryContext(active, health)).toMatchObject({
    missionId: 'mission-a',
    legId: 'leg-a',
    sourceIdentity: 'ctx-a',
  });
  expect(
    overviewAdvisoryContext(active, { ...health, operating_context_id: 'old' })
  ).toBeNull();
  expect(
    overviewAdvisoryContext({ ...active, leg_id: null }, health)
  ).toBeNull();
});
it('does not trust an all-available flag over misaligned source evidence even without events', () => {
  const data = snapshot([]);
  data.sources[0].aligned = false;
  expect(view(data).notice).toBe('Transport Advisories Unavailable');
});
