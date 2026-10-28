import type { ReactNode } from 'react';
import type { SavedRecord } from '@/types/operator';
import {
  sessionOutsideContext,
  type ConferenceAction,
} from './conferenceCommands';
import { conferenceCloseBlockers } from './callCommands';
import type { CallAssociation } from './callAssociation';
import { revisionUtc } from './revisionUtc';
import { eventUtc } from './eventFormatting';
const button =
  'min-h-11 rounded-lg border bg-background px-4 py-2 font-medium shadow-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50';
const primary =
  button + ' ws-conference-primary bg-primary text-primary-foreground';
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
  const discrepancy =
    connected > 0 &&
    (p.status === 'closed' || p.status === 'interrupted' || record.deleted);
  const status = discrepancy
    ? `Discrepancy · Customer Reported Connected; Conference ${record.deleted ? 'Removed' : p.status}. Continuity Unknown.`
    : blockers.length > 0
      ? 'Active Call Or Unresolved Customer Report · Resolve Before Closing.'
      : incomplete
        ? 'Activity Incomplete · Load Remaining Records Before Closing.'
        : previousSession
          ? 'Previous Session Not Assumed Available Here · Establish With The Two-Way Check For This Leg.'
          : p.status === 'closed'
            ? 'Closed · Establish To Reuse This Conference.'
            : p.status === 'interrupted'
              ? 'Connection Interrupted · Restore And Complete The Two-Way Check.'
              : ready
                ? 'Two-Way Check Complete · Connect Customer When Ready.'
                : p.status === 'established'
                  ? 'Earlier Check Not Recorded · Establish To Report The Completed Two-Way Check.'
                  : 'Establish After The Distant End Can Hear Us And We Can Hear Them.';
  return (
    <article
      id={`operator-record-${record.record_id}`}
      data-record-id={record.record_id}
      data-selected={selected || undefined}
      aria-label={`Conference ${p.title}`}
      className={
        'ws-conference-card min-w-0 space-y-2 rounded-xl border-2 border-l-4 p-4 break-words ' +
        (prominentActions
          ? 'border-teal-500/60 border-l-teal-500 bg-teal-500/5 shadow-md'
          : 'border-l-transparent bg-card shadow-sm') +
        (selected ? ' ring-2 ring-primary ring-offset-2' : '')
      }
    >
      <h4 className="text-xl font-bold">
        {p.title}
        {record.deleted ? ' · Removed' : ''}
      </h4>
      <p className="inline-block rounded-full border bg-background px-3 py-1 text-sm font-semibold">
        {previousSession
          ? 'Previous Session'
          : (p.status ?? 'Unknown').replace(/\b\w/g, (c) => c.toUpperCase())}
      </p>
      <p className="text-sm">
        Reported Transport: <strong>{transport(p.configured_transport)}</strong>
        {p.intended_transport && p.intended_transport !== p.configured_transport
          ? ` · Intended: ${transport(p.intended_transport)}`
          : ''}
      </p>
      {advisory}
      <div className="ws-conference-facts grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-muted-foreground">Two-Way Distant-End Check</p>
          <p title={revisionUtc(p.verified_at ?? null)}>
            {p.verified_at
              ? `${eventUtc(p.verified_at).slice(0, 16)} Zulu`
              : 'Unknown'}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Customers Reported Connected</p>
          <p>{connected}</p>
        </div>
      </div>
      <p
        className={
          'ws-conference-status rounded border border-transparent px-2 py-1 text-sm ' +
          (discrepancy
            ? 'border-amber-500 text-amber-500'
            : 'text-muted-foreground')
        }
        role={
          discrepancy ? 'alert' : blockers.length > 0 ? 'status' : undefined
        }
      >
        {status}
      </p>
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
      </div>
      <details className="border-t pt-3">
        <summary className="min-h-11 cursor-pointer py-2">
          Conference Details
        </summary>
        {compactActions && (
          <p className="text-sm">
            Last Reported Activity:{' '}
            {activityAssociationLabel ??
              (record.scope === 'mission'
                ? 'Association Unknown'
                : record.scope.replaceAll('_', ' '))}
            . Configuration Is Retained Across The Mission.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {!record.deleted && (
            <button
              className={button}
              disabled={disabled || incomplete || !ready}
              onClick={onJoin}
            >
              Connect Customer
            </button>
          )}
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
          Configuration Reported:{' '}
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
