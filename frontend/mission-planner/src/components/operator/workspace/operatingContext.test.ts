import { expect, it } from 'vitest';
import {
  defaultAssociation,
  operatingMission,
  operationalRelevant,
  replayCurrent,
} from './operatingContext';
import {
  record as savedRecord,
  input as noteInput,
  health,
} from '@/test/operator-fixtures';

it('follows active context but preserves an explicit historical browsing choice', () => {
  expect(operatingMission(null, { mission_id: 'active' })).toBe('active');
  expect(operatingMission('historical', { mission_id: 'active' })).toBe(
    'historical'
  );
  expect(operatingMission('', { mission_id: 'active' })).toBe('');
  expect(operatingMission(null, undefined)).toBe('');
});
it('defaults only a new record and keeps existing associations untouched', () => {
  const association = {
    scope: 'leg' as const,
    leg_id: 'leg-b',
    previous_leg_id: null,
    next_leg_id: null,
    label: 'Leg B',
  };
  const input = { ...noteInput, scope: 'mission' as const, leg_id: null };
  expect(defaultAssociation(input, association, false).leg_id).toBe('leg-b');
  expect(defaultAssociation(input, association, true)).toBe(input);
  expect(defaultAssociation(input, null, false)).toBe(input);
});
it('never counts retained simulation reports as current evidence in another replay', () => {
  const source = { ...health, mission_journal: true, replay_run_id: 'new' };
  expect(replayCurrent(savedRecord, source)).toBe(false);
  const report = {
    ...savedRecord,
    provenance: { ...savedRecord.provenance, replay_run_id: 'old' },
  };
  expect(replayCurrent(report, source)).toBe(false);
  expect(replayCurrent(report, { ...source, replay_run_id: 'old' })).toBe(true);
  expect(replayCurrent(report, { ...source, replay_run_id: null })).toBe(false);
  expect(replayCurrent(savedRecord, health)).toBe(true);
});

it('uses flight phase to choose preflight, ground gap, leg or postflight without inventing a leg', async () => {
  const { activeAssociation } = await import('./operatingContext');
  const mission = {
    id: 'm',
    name: 'Mission',
    legs: [
      { id: 'a', name: 'First' },
      { id: 'b', name: 'Second' },
    ],
  };
  const context = {
    state: 'available',
    mission_id: 'm',
    leg_id: 'a',
    leg_name: 'First',
    mission_name: 'Mission',
    phase: 'pre_departure',
    source_mode: 'simulation' as const,
    replay_run_id: 'r',
  };
  expect(activeAssociation(context, mission)?.scope).toBe('preflight');
  expect(
    activeAssociation({ ...context, phase: 'in_flight' }, mission)?.leg_id
  ).toBe('a');
  expect(
    activeAssociation({ ...context, phase: 'post_arrival' }, mission)
  ).toMatchObject({
    scope: 'between_legs',
    previous_leg_id: 'a',
    next_leg_id: 'b',
  });
  expect(
    activeAssociation(
      { ...context, leg_id: 'b', phase: 'post_arrival' },
      mission
    )?.scope
  ).toBe('postflight');
  expect(activeAssociation({ ...context, leg_id: null }, mission)).toBeNull();
  expect(
    activeAssociation(context, { ...mission, id: 'historical' })
  ).toBeNull();
});

it('retains unfulfilled mission requirements across replay changes without treating old connections as current', async () => {
  const { operationalRelevant } = await import('./operatingContext');
  const source = { ...health, mission_journal: true, replay_run_id: 'new' };
  const call = {
    ...savedRecord,
    time: { ...savedRecord.time, occurred_at: null },
    payload: {
      schema_version: 1 as const,
      entry_type: 'call' as const,
      title: 'Upcoming',
      note: '',
      previous_leg_id: null,
      next_leg_id: null,
      status: 'scheduled' as const,
      conference_id: null,
    },
  };
  expect(operationalRelevant(call, source)).toBe(true);
  expect(
    operationalRelevant(
      { ...call, payload: { ...call.payload, status: 'completed' } },
      source
    )
  ).toBe(false);
  expect(
    operationalRelevant(
      { ...call, time: { ...call.time, occurred_at: '2026-10-17T16:00:00Z' } },
      source
    )
  ).toBe(false);
});

it('keeps accepted conference definitions available without admitting historical session readiness', () => {
  const conference = {
    ...savedRecord,
    record_type: 'conference' as const,
    payload: {
      ...noteInput.payload,
      entry_type: 'conference' as const,
      status: 'established' as const,
      verified_at: '2026-10-17T16:00:00Z',
    },
  };
  const ordinary = {
    ...health,
    mission_journal: true,
    replay_run_id: null,
    operating_context_id: 'ordinary:runtime:1:route-a',
  };
  expect(operationalRelevant(conference, ordinary)).toBe(true);
  expect(replayCurrent(conference, ordinary)).toBe(false);
  const current = {
    ...conference,
    provenance: {
      ...conference.provenance,
      replay_run_id: null,
      operating_context_id: ordinary.operating_context_id,
    },
  };
  expect(replayCurrent(current, ordinary)).toBe(true);
  expect(
    replayCurrent(current, {
      ...ordinary,
      operating_context_id: 'ordinary:runtime:2:route-b',
    })
  ).toBe(false);
});
