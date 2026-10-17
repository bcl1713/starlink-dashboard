import type { SavedRecord } from '@/types/operator';
import type { ConferenceAction } from './conferenceCommands';
import { revisionUtc } from './revisionUtc';
const button = 'min-h-11 rounded border px-3 disabled:opacity-50';
export function ConferenceCard({
  record,
  participations,
  disabled,
  onAction,
  onEdit,
  onJoin,
  onHistory,
  onRemove,
}: {
  record: SavedRecord;
  participations: SavedRecord[];
  disabled: boolean;
  onAction: (action: ConferenceAction) => void;
  onEdit: () => void;
  onJoin: () => void;
  onHistory: () => void;
  onRemove: () => void;
}) {
  if (record.payload.entry_type !== 'conference') return null;
  const p = record.payload;
  const connected = participations.filter(
    (r) =>
      !r.deleted &&
      r.payload.entry_type === 'participation' &&
      r.payload.state === 'connected' &&
      r.payload.conference_id === record.record_id
  ).length;
  return (
    <article
      className="min-w-0 space-y-2 rounded border p-3 break-words"
      aria-label={`Conference ${p.title}`}
    >
      <h4 className="font-semibold">
        {p.title}
        {record.deleted ? ' · Removed' : ''}
      </h4>
      <p>
        Conference: {p.status ?? 'Unknown'} · Operator verification:{' '}
        {revisionUtc(p.verified_at ?? null)}
      </p>
      <p>Customer reported connected: {connected}</p>
      {connected > 0 &&
        (p.status === 'closed' ||
          p.status === 'interrupted' ||
          record.deleted) && (
          <p
            role="alert"
            className="rounded border-2 border-amber-500 p-2 font-semibold"
          >
            Discrepancy — customer reported connected; conference{' '}
            {record.deleted ? 'removed' : p.status}. Continuity unknown.
          </p>
        )}
      <p>
        Intended transport: {p.intended_transport ?? 'Unknown'} ·
        Operator-reported configuration: {p.configured_transport ?? 'Unknown'}
      </p>
      <p className="text-sm text-muted-foreground">
        Call-bearing transport and customer success are not independently
        verified.
      </p>
      <p className="text-sm">
        Configuration reported:{' '}
        {revisionUtc(p.configuration_reported_at ?? null)} · Coordinator:{' '}
        {p.coordinator ?? 'Unknown'}
      </p>
      <div className="flex flex-wrap gap-2">
        {!record.deleted && (
          <>
            {(!p.status ||
              ['unknown', 'preparing', 'closed'].includes(p.status)) && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('establish')}
              >
                Establish
              </button>
            )}
            {p.status === 'established' && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('verify')}
              >
                Verify
              </button>
            )}
            {p.status !== 'closed' && p.status !== 'interrupted' && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('interrupt')}
              >
                Interrupt conference
              </button>
            )}
            {p.status === 'interrupted' && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('restore_connection')}
              >
                Restore conference connection
              </button>
            )}
            {p.status !== 'closed' && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('close')}
              >
                Close conference
              </button>
            )}
            <button className={button} disabled={disabled} onClick={onJoin}>
              Customer Joined
            </button>
            <button className={button} disabled={disabled} onClick={onEdit}>
              Correct conference
            </button>
          </>
        )}
        <button className={button} disabled={disabled} onClick={onRemove}>
          {record.deleted ? 'Restore record' : 'Remove conference record'}
        </button>
        <button className={button} onClick={onHistory}>
          Conference history
        </button>
      </div>
    </article>
  );
}
