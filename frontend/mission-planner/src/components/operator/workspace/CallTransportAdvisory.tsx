import type { SavedRecord } from '@/types/operator';
import type { MissionTimelineSnapshot } from '@/types/missionTimeline';
import { eventUtc } from '../eventFormatting';
import { transportLabel } from '../transportLabel';
import { callTransportAdvisory } from './callTransportAdvisory';

export function CallTransportAdvisory({
  call,
  records,
  snapshot,
  stale,
}: {
  call: SavedRecord;
  records: SavedRecord[];
  snapshot?: MissionTimelineSnapshot;
  stale: boolean;
}) {
  const advisory = callTransportAdvisory(call, records, snapshot, stale);
  if (
    call.deleted ||
    (call.payload.entry_type === 'call' &&
      ['completed', 'cancelled'].includes(call.payload.status))
  )
    return null;
  return (
    <div
      className={`ws-call-advisory ${advisory.status === 'overlap' || advisory.status === 'advisory' ? 'ws-call-advisory-warning' : ''}`}
    >
      <p>
        Reported Transport: <strong>{advisory.assignment}</strong>
        {advisory.intended ? ` · Intended: ${advisory.intended}` : ''}
      </p>
      <p className="ws-meta">{advisory.reason}</p>
      {advisory.windows.map((event) => (
        <p key={event.event_id} className="text-sm">
          {event.kind === 'pop_advisory'
            ? 'PoP Transition Advisory'
            : event.advisory_type === 'concurrency_restriction'
              ? 'Coordinated Concurrency Restriction'
              : 'Scheduled Restriction'}{' '}
          · {transportLabel(event.transport)} · {eventUtc(event.due_at)} –{' '}
          {eventUtc(event.end_at)} · {call.payload.title}
        </p>
      ))}
    </div>
  );
}
