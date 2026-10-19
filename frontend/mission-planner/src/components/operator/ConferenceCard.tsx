import type { SavedRecord } from '@/types/operator';
import {
  sessionOutsideContext,
  type ConferenceAction,
} from './conferenceCommands';
import type { CallAssociation } from './callAssociation';
import { revisionUtc } from './revisionUtc';
const button =
  'min-h-11 rounded-lg border bg-background px-4 py-2 font-medium shadow-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50';
export function ConferenceCard({
  record,
  sessionCurrent = true,
  participations,
  disabled,
  onAction,
  onEdit,
  onJoin,
  compactActions = false,
  prominentActions = false,
  currentAssociation,
  activityAssociationLabel,
  onHistory,
  onRemove,
}: {
  sessionCurrent?: boolean;
  record: SavedRecord;
  participations: SavedRecord[];
  disabled: boolean;
  onAction: (action: ConferenceAction) => void;
  onEdit: () => void;
  compactActions?: boolean;
  prominentActions?: boolean;
  currentAssociation?: CallAssociation | null;
  activityAssociationLabel?: string;
  onJoin: () => void;
  onHistory: () => void;
  onRemove: () => void;
}) {
  if (record.payload.entry_type !== 'conference') return null;
  const p = record.payload;
  const previousSession =
    ['established', 'interrupted'].includes(p.status ?? '') &&
    (!sessionCurrent || sessionOutsideContext(record, currentAssociation));
  const connected = participations.filter(
    (r) =>
      !r.deleted &&
      r.payload.entry_type === 'participation' &&
      r.payload.state === 'connected' &&
      r.payload.conference_id === record.record_id
  ).length;
  return (
    <article
      className={
        'min-w-0 space-y-3 rounded-xl border p-4 break-words ' +
        (prominentActions
          ? 'border-2 border-l-4 border-teal-500/60 border-l-teal-500 bg-teal-500/5 shadow-md'
          : 'bg-card shadow-sm')
      }
      aria-label={`Conference ${p.title}`}
    >
      <h4 className="text-xl font-bold">
        {p.title}
        {record.deleted ? ' · Removed' : ''}
      </h4>
      <p className="rounded bg-muted p-2 text-sm">
        {previousSession
          ? 'This session is not assumed available here. Establish again for the current leg; previous reports remain in history.'
          : p.status === 'closed'
            ? 'Closed. Establish again to reuse this bridge.'
            : p.status === 'interrupted'
              ? 'Connection interrupted. Restore the bridge, then verify it again.'
              : p.status === 'established'
                ? p.verified_at
                  ? 'Bridge verification reported for this session. Report each customer joining and leaving.'
                  : 'Established. Verify the bridge next; each call test is reported separately.'
                : 'Next: establish this bridge, then verify it before use.'}
      </p>
      <p className="inline-block rounded-full border bg-background px-3 py-1 text-sm font-semibold">
        Conference: {previousSession ? 'Historical session report · ' : ''}
        {p.status ?? 'Unknown'} · Operator verification:{' '}
        {revisionUtc(p.verified_at ?? null)}
      </p>
      {compactActions && (
        <p>
          Last reported activity:{' '}
          {activityAssociationLabel ??
            (record.scope === 'mission'
              ? 'Association unknown'
              : record.scope.replaceAll('_', ' '))}
          . Saved configuration is kept across the mission.
        </p>
      )}
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
      <div className="flex flex-wrap gap-2">
        {!record.deleted && (
          <>
            {(!p.status ||
              ['unknown', 'preparing', 'closed'].includes(p.status) ||
              previousSession) && (
              <button
                className={button + ' bg-primary text-primary-foreground'}
                disabled={disabled}
                onClick={() => onAction('establish')}
              >
                {(p.status === 'closed' || previousSession) &&
                currentAssociation
                  ? `Reestablish · ${currentAssociation.label}`
                  : 'Establish'}
              </button>
            )}
            {!previousSession &&
              p.status === 'established' &&
              !p.verified_at && (
                <button
                  className={button}
                  disabled={disabled}
                  onClick={() => onAction('verify')}
                >
                  Verify
                </button>
              )}
            {!previousSession && p.status === 'interrupted' && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('restore_connection')}
              >
                Restore conference connection
              </button>
            )}
            {prominentActions && !previousSession && p.status !== 'closed' && (
              <button
                className={button}
                disabled={disabled}
                onClick={() => onAction('close')}
              >
                Close conference
              </button>
            )}
            <div className="flex flex-wrap gap-2">
              {!previousSession &&
                p.status !== 'closed' &&
                p.status !== 'interrupted' && (
                  <button
                    className={button}
                    disabled={disabled}
                    onClick={() => onAction('interrupt')}
                  >
                    Interrupt conference
                  </button>
                )}
              {!prominentActions &&
                !previousSession &&
                p.status !== 'closed' && (
                  <button
                    className={button}
                    disabled={disabled}
                    onClick={() => onAction('close')}
                  >
                    Close conference
                  </button>
                )}
              {(!compactActions || prominentActions) && (
                <button className={button} disabled={disabled} onClick={onJoin}>
                  Customer Joined
                </button>
              )}
              <button className={button} disabled={disabled} onClick={onEdit}>
                Correct conference
              </button>
            </div>
          </>
        )}
      </div>
      <div className="flex flex-wrap gap-2 border-t pt-3">
        <button className={button} onClick={onHistory}>
          Conference history
        </button>
        <button className={button} disabled={disabled} onClick={onRemove}>
          {record.deleted ? 'Restore record' : 'Remove conference record'}
        </button>
      </div>
      <p>
        Intended transport: {p.intended_transport ?? 'Unknown'} ·
        Operator-reported configuration: {p.configured_transport ?? 'Unknown'}
      </p>
      {compactActions && (
        <p className="text-sm text-muted-foreground">
          Close at leg end. Configuration stays saved; a later leg requires an
          explicit reestablishment and verification.
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        Closing this bridge does not disconnect customer reports or finish
        calls.
      </p>
      <p className="text-sm">
        Configuration reported:{' '}
        {revisionUtc(p.configuration_reported_at ?? null)} · Coordinator:{' '}
        {p.coordinator ?? 'Unknown'}
      </p>
    </article>
  );
}
