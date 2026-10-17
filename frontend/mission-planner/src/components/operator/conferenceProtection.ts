import type { SavedRecord, Transport } from '@/types/operator';
import type { Timeline } from '@/services/timeline';
export type LegProtectionSource = { legId: string; timeline: Timeline | null };
export interface ProtectionItem {
  legId: string;
  participationId: string;
  source: string;
  sourceIds: string[];
  revision: string | null;
  start: string;
  end: string;
  classification: string;
  relevance: 'configured' | 'intended' | 'unknown' | 'call';
  computedAt: string;
}
export interface ProtectionSnapshot {
  asOf: string;
  coverage: 'available' | 'partial' | 'unknown';
  items: ProtectionItem[];
  limitations: string[];
}
export function deriveProtection(
  records: SavedRecord[],
  sources: LegProtectionSource[],
  asOf: string,
  recordsComplete: boolean
): ProtectionSnapshot {
  const result: ProtectionSnapshot = {
    asOf,
    coverage: 'available',
    items: [],
    limitations: [
      'Modeled restrictions only. Operator-planned transport changes are not included.',
    ],
  };
  const active = records.filter((r) => !r.deleted);
  const now = Date.parse(asOf);
  let good = 0;
  let partial =
    !recordsComplete || !Number.isFinite(now) || sources.length === 0;
  const seen = new Set<string>();
  for (const { legId, timeline } of sources) {
    if (!timeline || timeline.mission_leg_id !== legId) {
      partial = true;
      continue;
    }
    good++;
    // A successful read of a saved plan does not prove alignment with current inputs.
    if (
      Date.parse(timeline.created_at) !== now ||
      !timeline.pop_forecast ||
      !['ready', 'disabled'].includes(timeline.pop_forecast.status) ||
      !timeline.call_continuity
    )
      partial = true;
    for (const customer of active) {
      if (
        customer.payload.entry_type !== 'participation' ||
        customer.payload.state !== 'connected'
      )
        continue;
      const payload = customer.payload;
      const conference = active.find(
        (r) => r.record_id === payload.conference_id
      )?.payload;
      const configured =
        conference?.entry_type === 'conference'
          ? conference.configured_transport
          : null;
      const intended =
        conference?.entry_type === 'conference'
          ? conference.intended_transport
          : null;
      const call = active.find((r) => r.record_id === payload.call_id);
      const plannedEnd = Date.parse(call?.time.planned_end_at ?? '');
      const horizonEnd =
        Number.isFinite(plannedEnd) && plannedEnd > now ? plannedEnd : Infinity;
      const append = (
        source: string,
        id: string[],
        revision: string | null,
        start: string,
        end: string,
        classification: string,
        transport?: Transport
      ) => {
        const a = Date.parse(start),
          b = Date.parse(end);
        if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) {
          partial = true;
          return;
        }
        if (a >= horizonEnd || b <= now) return;
        let relevance: ProtectionItem['relevance'] = 'call';
        if (transport) {
          if (transport === configured) relevance = 'configured';
          else if (transport === intended) relevance = 'intended';
          else if (!configured && !intended) relevance = 'unknown';
          else return;
        }
        const key = JSON.stringify([
          legId,
          customer.record_id,
          source,
          id,
          start,
          end,
          classification,
        ]);
        if (seen.has(key)) return;
        seen.add(key);
        result.items.push({
          legId,
          participationId: customer.record_id,
          source,
          sourceIds: id,
          revision,
          start,
          end,
          classification,
          relevance,
          computedAt: timeline.created_at,
        });
      };
      if (timeline.pop_forecast?.status === 'ready')
        for (const window of timeline.pop_forecast.transitions)
          append(
            'pop',
            [window.crossing.id],
            timeline.pop_forecast.revision,
            window.window_start_utc,
            window.window_end_utc,
            'advisory',
            'Starshield'
          );
      for (const interval of timeline.call_continuity?.intervals ?? [])
        if (interval.classification !== 'ordinary')
          append(
            'continuity',
            [...interval.transition_ids, ...interval.source_ids],
            timeline.call_continuity!.revision,
            interval.start_utc,
            interval.end_utc,
            interval.classification
          );
      for (const segment of timeline.segments) {
        for (const [transport, state] of [
          ['Ka', segment.ka_state],
          ['X', segment.x_state],
          ['Starshield', segment.ku_state],
        ] as const) {
          if (state === 'offline' || state === 'degraded')
            append(
              'segment',
              [segment.id, transport],
              timeline.call_capability_revision ?? null,
              segment.start_time,
              segment.end_time,
              `modeled_${state}`,
              transport
            );
          else if (state !== 'available') partial = true;
        }
      }
    }
  }
  result.coverage = good === 0 ? 'unknown' : partial ? 'partial' : 'available';
  if (partial)
    result.limitations.push(
      'Coverage is partial or freshness/input alignment is unknown. Saved timelines may be stale; no all-clear is implied.'
    );
  if (!recordsComplete)
    result.limitations.push('Some operational records have not loaded.');
  return result;
}
