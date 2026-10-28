import type { ReactNode } from 'react';
import type { SavedRecord } from '@/types/operator';
import {
  sessionOutsideContext,
  type ConferenceAction,
} from './conferenceCommands';
import { conferenceCloseBlockers } from './callCommands';
import type { CallAssociation } from './callAssociation';
import { revisionUtc } from './revisionUtc';
const button =
  'min-h-11 rounded-lg border bg-background px-4 py-2 font-medium shadow-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50';
const primary = button + ' min-w-40 bg-primary text-primary-foreground';
const transport = (id: string | null | undefined) =>
  id === 'Ka' ? 'Ka Commercial' : id === 'X' ? 'X-Band' : (id ?? 'Unknown');
export function ConferenceCard({
  record,
  sessionCurrent = true,
  participations,
  calls = [],
  incomplete = false,
  selected = false,
  advisory,
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
  calls?: SavedRecord[];
  incomplete?: boolean;
  selected?: boolean;
  advisory?: ReactNode;
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
  const blockers = conferenceCloseBlockers(record, [
    ...calls,
    ...participations,
  ]);
  const closeDisabled = disabled || incomplete || blockers.length > 0;
  const ready =
    !previousSession && p.status === 'established' && !!p.verified_at;
  const needsEstablish =
    previousSession ||
    !['established', 'interrupted'].includes(p.status ?? '') ||
    (p.status === 'established' && !p.verified_at);
  return (
    <article
      id={`operator-record-${record.record_id}`}
      data-record-id={record.record_id}
      data-selected={selected || undefined}
      aria-label={`Conference ${p.title}`}
      className={
        'min-w-0 space-y-3 rounded-xl border-2 border-l-4 p-4 break-words ' +
        (prominentActions
          ? 'border-2 border-l-4 border-teal-500/60 border-l-teal-500 bg-teal-500/5 shadow-md'
          : 'border-l-transparent bg-card shadow-sm') +
        (selected ? ' ring-2 ring-primary ring-offset-2' : '')
      }
    >
      <h4 className="text-xl font-bold">
        {p.title}
        {record.deleted ? ' · Removed' : ''}
      </h4>
      <p className="min-h-24 rounded bg-muted p-2 text-sm">
        {previousSession
          ? 'This session is not assumed available here. Establish again for the current leg; previous reports remain in history.'
          : p.status === 'closed'
            ? 'Closed. Establish again to reuse this bridge.'
            : p.status === 'interrupted'
              ? 'Connection interrupted. Restore the bridge, then Establish with the two-way check.'
              : ready
                ? 'Established with a two-way distant-end check. Connect Customer when ready.'
                : p.status === 'established'
                  ? 'Earlier establishment has no completed two-way check. Establish to report the check; earlier evidence stays in history.'
                  : 'Establish includes the two-way distant-end check. Then Connect Customer.'}
      </p>
      <p className="inline-block min-h-20 rounded-full border bg-background px-3 py-1 text-sm font-semibold">
        Conference: {previousSession ? 'Historical session report · ' : ''}
        {p.status ?? 'Unknown'} · Two-way check:{' '}
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
      <div
        className="flex min-h-11 flex-wrap items-start gap-2"
        aria-label="Conference primary action"
      >
        {!record.deleted &&
          (needsEstablish ? (
            <button
              className={primary}
              disabled={disabled}
              onClick={() => onAction('establish')}
            >
              Establish
            </button>
          ) : (
            <button
              className={primary}
              disabled={closeDisabled}
              onClick={() => onAction('close')}
            >
              Close Conference
            </button>
          ))}
        {!record.deleted && (
          <button
            className={button}
            disabled={disabled || incomplete || !ready}
            onClick={onJoin}
          >
            Connect Customer
          </button>
        )}
      </div>
      <p className="min-h-16 text-sm text-muted-foreground">
        {blockers.length > 0
          ? 'Finish active calls and resolve connected or unknown customer reports before closing.'
          : incomplete
            ? 'Load remaining activity before closing.'
            : 'Establish reports the two-way check; Close keeps the saved bridge available for reuse.'}
      </p>
      <p>
        Intended Transport: {transport(p.intended_transport)} ·
        Operator-reported configuration: {transport(p.configured_transport)}
      </p>
      {advisory}
      <details className="border-t pt-3">
        <summary className="min-h-11 cursor-pointer py-2">
          Conference Details
        </summary>
        <div className="flex flex-wrap gap-2">
          {!record.deleted && (
            <>
              {!previousSession && p.status === 'interrupted' && (
                <button
                  className={button}
                  disabled={disabled}
                  onClick={() => onAction('restore_connection')}
                >
                  Restore Conference Connection
                </button>
              )}
              {!previousSession &&
                !['closed', 'interrupted'].includes(p.status ?? '') && (
                  <button
                    className={button}
                    disabled={disabled}
                    onClick={() => onAction('interrupt')}
                  >
                    Interrupt Conference
                  </button>
                )}
              {needsEstablish && p.status !== 'closed' && (
                <button
                  className={button}
                  disabled={closeDisabled}
                  onClick={() => onAction('close')}
                >
                  Close Unverified Session
                </button>
              )}
              <button className={button} disabled={disabled} onClick={onEdit}>
                Correct Conference
              </button>
            </>
          )}
          <button className={button} onClick={onHistory}>
            Conference History
          </button>
          <button className={button} disabled={disabled} onClick={onRemove}>
            {record.deleted ? 'Restore Record' : 'Remove Conference Record'}
          </button>
        </div>
        <p className="text-sm">
          Configuration reported:{' '}
          {revisionUtc(p.configuration_reported_at ?? null)} · Coordinator:{' '}
          {p.coordinator ?? 'Unknown'}
        </p>
        <p className="text-sm text-muted-foreground">
          Operator reports do not control hardware. Closing never finishes calls
          or changes customer intervals.
        </p>
      </details>
    </article>
  );
}
