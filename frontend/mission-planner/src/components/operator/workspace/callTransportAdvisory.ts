import type { SavedRecord } from '@/types/operator';
import type { OperationalEvent } from '@/types/operatorEvents';
import type { MissionTimelineSnapshot } from '@/types/missionTimeline';
import { transportLabel } from '../transportLabel';

function key(value: string | null | undefined) {
  return value
    ? ({
        KA: 'Ka',
        ka: 'Ka',
        Ku: 'Starshield',
        Starlink: 'Starshield',
        'X-band': 'X',
      }[value] ?? value)
    : null;
}
const time = (value: string | null | undefined) => Date.parse(value ?? '');
export function callTransportAdvisory(
  call: SavedRecord,
  records: SavedRecord[],
  snapshot: MissionTimelineSnapshot | undefined,
  stale: boolean
): {
  status: 'unknown' | 'overlap' | 'advisory' | 'no_known_overlap';
  assignment: string;
  intended: string | null;
  reason: string;
  windows: OperationalEvent[];
} {
  const payload = call.payload.entry_type === 'call' ? call.payload : null;
  const bridge = payload?.conference_id
    ? records.find((r) => r.record_id === payload.conference_id && !r.deleted)
    : undefined;
  const conference =
    bridge?.payload.entry_type === 'conference' ? bridge.payload : null;
  const assigned = payload?.conference_id
    ? conference?.configured_transport
    : payload?.direct_transport;
  const intended =
    conference?.intended_transport && conference.intended_transport !== assigned
      ? transportLabel(conference.intended_transport)
      : null;
  const base = {
    assignment: transportLabel(assigned),
    intended,
    windows: [] as OperationalEvent[],
  };
  const unknown = (reason: string) => ({
    ...base,
    status: 'unknown' as const,
    reason,
  });
  if (!assigned)
    return unknown('Reported Transport Unknown · Schedule Coverage Unknown');
  if (!['Ka', 'X', 'Starshield'].includes(key(assigned)!))
    return unknown('Ad Hoc Transport · Integrated Schedule Unavailable');
  const start = time(call.time.planned_start_at);
  const end = time(call.time.planned_end_at);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start)
    return unknown('Call Timing Incomplete · Schedule Coverage Unknown');
  if (!snapshot || snapshot.mission_id !== call.mission_id || stale)
    return unknown('Schedule Unavailable Or Stale');
  const applicable = snapshot.events.filter(
    (e) =>
      e.mission_id === call.mission_id &&
      (!call.leg_id || !e.leg_id || e.leg_id === call.leg_id) &&
      (e.kind === 'restriction' ||
        (e.kind === 'pop_advisory' &&
          e.advisory_type === 'transition_window')) &&
      (e.transport === null || key(e.transport) === key(assigned))
  );
  const windows = applicable.filter(
    (e) =>
      e.freshness === 'fresh' &&
      Number.isFinite(time(e.due_at)) &&
      Number.isFinite(time(e.end_at)) &&
      time(e.due_at) < end &&
      time(e.end_at) > start
  );
  if (windows.length) {
    const restriction = windows.some((e) => e.kind === 'restriction');
    return {
      ...base,
      windows,
      status: restriction ? 'overlap' : 'advisory',
      reason: restriction
        ? 'Scheduled Restriction Overlap · Advisory Only'
        : 'PoP Transition Advisory · Not An Observed Outage',
    };
  }
  if (
    applicable.some(
      (e) =>
        e.freshness !== 'fresh' ||
        !Number.isFinite(time(e.due_at)) ||
        !Number.isFinite(time(e.end_at))
    )
  )
    return unknown('Restriction Timing Or Freshness Unknown');
  const coverage = snapshot.legs.some(
    (leg) =>
      leg.coverage === 'available' &&
      (!call.leg_id || leg.leg_id === call.leg_id) &&
      time(leg.scheduled_departure_at) <= start &&
      time(leg.scheduled_arrival_at) >= end &&
      snapshot.sources.some(
        (s) =>
          s.source === `model:${leg.leg_id}` &&
          s.aligned &&
          s.freshness === 'fresh'
      )
  );
  return coverage
    ? {
        ...base,
        status: 'no_known_overlap',
        reason: 'No Known Overlap In Available Schedule · Model Estimate',
      }
    : unknown('Integrated Schedule Coverage Unknown');
}
