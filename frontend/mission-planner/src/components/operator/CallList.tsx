import type { ReactNode } from 'react';
import type { ReadRecord, SavedRecord } from '@/types/operator';
import { preparationAt } from './callTiming';
import { customerConnectionReady, type CallAction } from './callCommands';
import {
  sessionOutsideContext,
  type ConferenceAction,
} from './conferenceCommands';
import type { CallAssociation } from './callAssociation';
const callUtc = (value: string | null) =>
  value
    ? `${new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))} Zulu`
    : 'Unknown';
const button =
  'min-h-11 rounded-lg border bg-background px-4 py-2 font-medium shadow-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50';
export function CallList({
  items,
  activeOnly = false,
  archivedOnly = false,
  disabled,
  incomplete,
  asOf,
  onEdit,
  onHistory,
  onTransition,
  onCallAction,
  onConferenceAction,
  onCustomerAction,
  currentAssociation,
  isSessionCurrent = () => true,
  selectedRecordId,
  renderAdvisory,
}: {
  isSessionCurrent?: (record: SavedRecord) => boolean;
  selectedRecordId?: string | null;
  renderAdvisory?: (call: SavedRecord) => ReactNode;
  items: ReadRecord[];
  activeOnly?: boolean;
  archivedOnly?: boolean;
  disabled: boolean;
  incomplete: boolean;
  asOf?: string;
  onEdit: (record: SavedRecord) => void;
  onHistory: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
  currentAssociation?: CallAssociation | null;
  onCallAction?: (record: SavedRecord, intent: CallAction) => void;
  onConferenceAction?: (record: SavedRecord, intent: ConferenceAction) => void;
  onCustomerAction?: (
    record: SavedRecord,
    intent: 'left' | 'interrupted' | 'restore'
  ) => void;
}) {
  const unique = [
    ...new Map(
      items
        .filter((i) => i.record.record_type === 'call')
        .map((i) => [i.record.record_id, i])
    ).values(),
  ];
  const ordered = unique.sort((a, b) => {
    const av = Date.parse(a.record.time.planned_start_at ?? '');
    const bv = Date.parse(b.record.time.planned_start_at ?? '');
    const delta =
      (Number.isFinite(av) ? av : Infinity) -
      (Number.isFinite(bv) ? bv : Infinity);
    return (
      (Number.isNaN(delta) ? 0 : delta) ||
      a.record.record_id.localeCompare(b.record.record_id)
    );
  });
  const active = ordered.filter(
    (i) =>
      !i.record.deleted &&
      i.record.payload.entry_type === 'call' &&
      !['completed', 'cancelled'].includes(i.record.payload.status)
  );
  function rows(values: ReadRecord[]) {
    return values.map((item) => {
      const r = item.record;
      if (r.payload.entry_type !== 'call') return null;
      const prep = preparationAt(r);
      const payload = r.payload;
      const records = items.map((item) => item.record);
      const bridge = records.find(
        (record) =>
          record.record_id === payload.conference_id &&
          !record.deleted &&
          record.payload.entry_type === 'conference'
      );
      const previousSession =
        bridge &&
        bridge.payload.entry_type === 'conference' &&
        ['established', 'interrupted'].includes(bridge.payload.status ?? '') &&
        (!isSessionCurrent(bridge) ||
          sessionOutsideContext(bridge, currentAssociation));
      const bridgePayload =
        bridge?.payload.entry_type === 'conference' ? bridge.payload : null;
      const customers = records.filter(
        (record) =>
          !record.deleted &&
          record.payload.entry_type === 'participation' &&
          record.payload.call_id === r.record_id
      );
      const connected = customers.filter(
        (record) =>
          record.payload.entry_type === 'participation' &&
          record.payload.state === 'connected'
      );
      const ongoing =
        !r.deleted && !['completed', 'cancelled'].includes(payload.status);
      const ready = customerConnectionReady(
        r,
        records,
        (target) =>
          isSessionCurrent(target) &&
          (target.record_type !== 'conference' ||
            !sessionOutsideContext(target, currentAssociation))
      );
      const direct = !payload.conference_id;
      return (
        <li
          key={r.record_id}
          id={`operator-record-${r.record_id}`}
          data-record-id={r.record_id}
          data-selected={selectedRecordId === r.record_id || undefined}
          className={
            'min-w-0 space-y-3 break-words rounded-xl border p-4 [overflow-wrap:anywhere] ' +
            (ongoing && onCallAction
              ? 'border-2 border-l-4 border-l-sky-500 border-sky-500/60 bg-sky-500/5 shadow-md'
              : 'bg-card shadow-sm') +
            (selectedRecordId === r.record_id
              ? ' ring-2 ring-primary ring-offset-2'
              : '')
          }
        >
          <h4 className="text-xl font-bold">
            {r.payload.party ?? r.payload.title}
          </h4>
          <p className="inline-block rounded-full border bg-background px-3 py-1 text-sm font-semibold">
            {r.deleted ? 'Removed · ' : ''}
            {r.payload.status === 'cancelled'
              ? 'Canceled'
              : r.time.occurred_at && ongoing
                ? 'In progress'
                : r.payload.status}{' '}
            · {r.payload.communications_kind ?? 'Type unknown'}
          </p>
          <p className="text-sm">
            Planned: {callUtc(r.time.planned_start_at)} · End:{' '}
            {callUtc(r.time.planned_end_at)}
          </p>
          <p className="text-sm">
            Actual: {callUtc(r.time.occurred_at)} · End:{' '}
            {callUtc(r.time.ended_at)}
          </p>
          {prep && (
            <p className="text-sm">
              Prepare: {callUtc(prep)}
              {asOf
                ? Date.parse(prep) <= Date.parse(asOf)
                  ? ' · Due at snapshot'
                  : ' · Upcoming at snapshot'
                : ''}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Operator reported · freshness {item.freshness.status} · association{' '}
            {item.association.status} · {r.scope.replaceAll('_', ' ')}
          </p>
          {onCallAction && (
            <>
              <p className="text-sm">
                Bridge:{' '}
                {previousSession && bridgePayload?.status !== 'closed'
                  ? 'Previous activity report · not assumed available here · '
                  : ''}
                {bridgePayload?.title ? `${bridgePayload.title} · ` : ''}
                {bridgePayload
                  ? `${bridgePayload.status ?? 'unknown'} · ${bridgePayload.verified_at ? 'verification reported' : 'not verified'}`
                  : payload.conference_id
                    ? 'Unresolved'
                    : 'Direct Connection'}
              </p>
              <p className="text-sm">
                Customer:{' '}
                {connected.length
                  ? `${connected.length} reported connected`
                  : incomplete
                    ? 'Reports incomplete'
                    : customers.length
                      ? 'No current connection reported'
                      : 'No connection reported'}{' '}
                · Two-way check:{' '}
                {direct
                  ? payload.established_at
                    ? 'reported'
                    : 'not reported'
                  : bridgePayload?.verified_at
                    ? 'reported'
                    : 'not reported'}
              </p>
              <p className="text-xs text-muted-foreground">
                Operator reports; these actions do not control hardware.
              </p>
              {ongoing && (
                <div className="flex flex-wrap gap-2">
                  {direct && !ready && (
                    <button
                      className={button + ' bg-primary text-primary-foreground'}
                      disabled={disabled}
                      onClick={() => onCallAction(r, 'establish')}
                    >
                      Establish
                    </button>
                  )}
                  {bridge && bridgePayload && onConferenceAction && (
                    <>
                      {(['preparing', 'unknown', 'closed'].includes(
                        bridgePayload.status ?? 'unknown'
                      ) ||
                        previousSession ||
                        (bridgePayload.status === 'established' &&
                          !bridgePayload.verified_at)) && (
                        <button
                          className={button}
                          disabled={disabled}
                          onClick={() =>
                            onConferenceAction(bridge, 'establish')
                          }
                        >
                          Establish Bridge
                        </button>
                      )}
                      {!previousSession &&
                        bridgePayload.status === 'interrupted' && (
                          <button
                            className={button}
                            disabled={disabled}
                            onClick={() =>
                              onConferenceAction(bridge, 'restore_connection')
                            }
                          >
                            Restore Bridge
                          </button>
                        )}
                    </>
                  )}
                  {!connected.length && (
                    <button
                      className={button + ' bg-primary text-primary-foreground'}
                      disabled={disabled || incomplete || !ready}
                      onClick={() => onCallAction(r, 'connect')}
                    >
                      Connect Customer
                    </button>
                  )}
                  {r.time.occurred_at && (
                    <>
                      {connected.map((customer) => (
                        <button
                          key={customer.record_id}
                          className={button}
                          disabled={disabled}
                          onClick={() => onCustomerAction?.(customer, 'left')}
                        >
                          Report Customer Left
                          {connected.length > 1 &&
                          customer.payload.entry_type === 'participation'
                            ? ` · ${customer.payload.participant ?? customer.payload.title}`
                            : ''}
                        </button>
                      ))}
                      <button
                        className={button}
                        disabled={
                          disabled || incomplete || connected.length > 0
                        }
                        onClick={() => onCallAction(r, 'finish')}
                      >
                        Finish Call
                      </button>
                      {connected.length > 0 && (
                        <p className="text-sm">
                          Report the customer leaving before finishing. The
                          bridge stays available for reuse.
                        </p>
                      )}
                    </>
                  )}
                  <button
                    className={button}
                    disabled={disabled || !!r.time.occurred_at}
                    onClick={() => onCallAction(r, 'cancel')}
                  >
                    Cancel Call
                  </button>
                </div>
              )}
            </>
          )}
          {renderAdvisory?.(r)}
          <div className="flex flex-wrap gap-2">
            <button
              className={button}
              disabled={disabled || r.deleted}
              onClick={() => onEdit(r)}
            >
              {onCallAction && ongoing && !r.time.occurred_at
                ? 'Reschedule'
                : 'Edit Call'}
            </button>
            <button className={button} onClick={() => onHistory(r.record_id)}>
              Call History
            </button>
            <button
              className={button}
              disabled={disabled}
              onClick={() => onTransition(r)}
            >
              {r.deleted ? 'Restore Call' : 'Remove Call'}
            </button>
          </div>
        </li>
      );
    });
  }
  return (
    <div className="min-w-0 space-y-3" aria-label="Call list">
      {incomplete && (
        <p role="status">
          Call list incomplete. Load more calls to include remaining records.
        </p>
      )}
      {!archivedOnly && (
        <>
          {!activeOnly && (
            <h3 className="font-semibold">Active requirements</h3>
          )}
          {!active.length && <p>No recorded active requirements.</p>}
          <ul className="space-y-3">
            {rows(active.filter((i) => !!i.record.time.planned_start_at))}
          </ul>
          {active.some((i) => !i.record.time.planned_start_at) && (
            <>
              <h4 className="font-medium">Unknown planned timing</h4>
              <ul className="space-y-3">
                {rows(active.filter((i) => !i.record.time.planned_start_at))}
              </ul>
            </>
          )}
        </>
      )}
      {!activeOnly && (
        <details>
          <summary className="min-h-11 cursor-pointer py-2">
            Completed, canceled and removed calls
          </summary>
          <ul className="space-y-3">
            {rows(ordered.filter((i) => !active.includes(i)))}
          </ul>
        </details>
      )}
    </div>
  );
}
