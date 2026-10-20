import type { SavedRecord } from '@/types/operator';
import { revisionUtc } from './revisionUtc';
export function ParticipationRow({
  record,
  conference,
  call,
  disabled,
  onAction,
  onEdit,
  onHistory,
  onRemove,
}: {
  record: SavedRecord;
  conference?: SavedRecord;
  call?: SavedRecord;
  disabled: boolean;
  onAction: (action: 'left' | 'interrupted' | 'restore') => void;
  onEdit: () => void;
  onHistory: () => void;
  onRemove: () => void;
}) {
  if (record.payload.entry_type !== 'participation') return null;
  const p = record.payload;
  const discrepancy =
    p.state === 'connected' &&
    conference?.payload.entry_type === 'conference' &&
    (conference.deleted ||
      conference.payload.status === 'closed' ||
      conference.payload.status === 'interrupted');
  return (
    <article
      aria-label={`Customer ${p.participant ?? 'Unknown'}`}
      className="space-y-2 rounded border p-3 break-words"
    >
      <h4 className="font-semibold">
        {p.participant ?? 'Unknown customer'} · {p.state ?? 'Unknown'}
        {record.deleted ? ' · Removed' : ''}
      </h4>
      <p>
        Call: {call?.payload.title ?? p.call_id ?? 'Unassigned'} · Conference:{' '}
        {conference?.payload.title ?? p.conference_id ?? 'Unassigned'}
      </p>
      <p>
        Reported join: {revisionUtc(record.time.occurred_at)} · End:{' '}
        {revisionUtc(record.time.ended_at)} · {record.time.end_state}
      </p>
      {p.state === 'connected' && !record.deleted && (
        <p className="font-semibold">
          Protected customer activity · operator reported
        </p>
      )}
      {discrepancy && (
        <p role="alert" className="border-2 border-amber-500 p-2 font-semibold">
          Discrepancy — conference unavailable; customer remains reported
          connected. Continuity unknown.
        </p>
      )}
      {p.resumes_participation_id && (
        <p className="text-sm">
          Connection restored as a new interval; previous interruption retained.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {!record.deleted && (
          <>
            {p.state === 'connected' && (
              <>
                <button disabled={disabled} onClick={() => onAction('left')}>
                  Customer Left
                </button>
                <button
                  disabled={disabled}
                  onClick={() => onAction('interrupted')}
                >
                  Interrupt customer
                </button>
              </>
            )}
            {p.state === 'interrupted' && (
              <button disabled={disabled} onClick={() => onAction('restore')}>
                Restore connection
              </button>
            )}
            <button disabled={disabled} onClick={onEdit}>
              Correct customer interval
            </button>
          </>
        )}
        <button disabled={disabled} onClick={onRemove}>
          {record.deleted ? 'Restore record' : 'Remove customer record'}
        </button>
        <button onClick={onHistory}>Customer history</button>
      </div>
    </article>
  );
}
