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
      const interrupted = customers.find(
        (customer) =>
          customer.payload.entry_type === 'participation' &&
          customer.payload.state === 'interrupted'
      );
      const customerLeft = (customer: SavedRecord) =>
        'Report Customer Left' +
        (connected.length > 1 && customer.payload.entry_type === 'participation'
          ? ` · ${customer.payload.participant ?? customer.payload.title}`
          : '');
      const canFinish =
        !!r.time.occurred_at && !incomplete && connected.length === 0;
      const finishedCustomers =
        customers.length > 0 &&
        customers.every(
          (customer) =>
            customer.payload.entry_type === 'participation' &&
            customer.payload.state === 'left'
        );
      let primary: {
        label: string;
        disabled: boolean;
        run: () => void;
      } | null = null;
      if (ongoing && onCallAction) {
        if (connected.length) {
          primary = {
            label: customerLeft(connected[0]),
            disabled: disabled || !onCustomerAction,
            run: () => onCustomerAction?.(connected[0], 'left'),
          };
        } else if (r.time.occurred_at && finishedCustomers) {
          primary = {
            label: 'Finish Call',
            disabled: disabled || !canFinish,
            run: () => onCallAction(r, 'finish'),
          };
        } else if (!ready) {
          if (direct)
            primary = {
              label: 'Establish',
              disabled,
              run: () => onCallAction(r, 'establish'),
            };
          else if (bridge && bridgePayload && onConferenceAction) {
            const restore =
              !previousSession && bridgePayload.status === 'interrupted';
            primary = {
              label: restore ? 'Restore Bridge' : 'Establish Bridge',
              disabled,
              run: () =>
                onConferenceAction(
                  bridge,
                  restore ? 'restore_connection' : 'establish'
                ),
            };
          } else
            primary = {
              label: 'Choose Conference',
              disabled,
              run: () => onEdit(r),
            };
        } else if (interrupted && onCustomerAction) {
          primary = {
            label: 'Restore Customer',
            disabled: disabled || incomplete,
            run: () => onCustomerAction(interrupted, 'restore'),
          };
        } else
          primary = {
            label: 'Connect Customer',
            disabled: disabled || incomplete,
            run: () => onCallAction(r, 'connect'),
          };
      }
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
                ? 'In Progress'
                : r.payload.status.replace(/\b\w/g, (c) => c.toUpperCase())}
            {r.payload.communications_kind &&
              ` · ${{ voice: 'Voice', vtc: 'VTC', other: 'Other' }[r.payload.communications_kind]}`}
          </p>
          <p className="text-sm">
            Planned: {callUtc(r.time.planned_start_at)} · End:{' '}
            {callUtc(r.time.planned_end_at)}
          </p>
          {renderAdvisory?.(r)}
          {r.time.occurred_at && (
            <p className="text-sm">
              Actual: {callUtc(r.time.occurred_at)}
              {r.time.ended_at ? ` · End: ${callUtc(r.time.ended_at)}` : ''}
            </p>
          )}
          <p className="text-sm">
            {payload.conference_id
              ? `Conference: ${bridgePayload?.title ?? 'Unavailable'}`
              : 'Direct Connection'}
            {connected.length
              ? ` · ${connected.length} Customer${connected.length === 1 ? '' : 's'} Connected`
              : ''}
          </p>
          {onCallAction && ongoing && (
            <>
              {payload.conference_id && !bridge && (
                <p role="status">
                  Conference unavailable. Choose a conference before connecting.
                </p>
              )}
              {previousSession && (
                <p role="status">
                  Previous activity report. Establish this conference in the
                  current context before connecting.
                </p>
              )}
              {bridgePayload?.status === 'established' &&
                !bridgePayload.verified_at && (
                  <p role="status">
                    Complete establishment before connecting the customer.
                  </p>
                )}
              {interrupted && (
                <p role="status">Customer connection interrupted.</p>
              )}
              {incomplete && (
                <p role="status">
                  Customer reports incomplete. Load remaining records before
                  connecting or finishing.
                </p>
              )}
              {item.freshness.status === 'stale' && (
                <p role="status">
                  Last-known call report. Refresh before using this state.
                </p>
              )}
              {item.association.status !== 'resolved' && (
                <p role="status">
                  Call association {item.association.status}. Review Call
                  Details.
                </p>
              )}
            </>
          )}
          {primary && (
            <button
              className={button + ' ws-primary'}
              data-primary-action
              disabled={primary.disabled}
              onClick={primary.run}
            >
              {primary.label}
            </button>
          )}
          <details className="border-t pt-3">
            <summary className="min-h-11 cursor-pointer py-2">
              Call Details
            </summary>
            <div className="space-y-3 pt-2">
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
                Operator reported · freshness {item.freshness.status} ·
                association {item.association.status} ·{' '}
                {r.scope.replaceAll('_', ' ')}
              </p>
              {bridgePayload && (
                <p className="text-sm">
                  Conference status: {bridgePayload.status ?? 'unknown'}
                  {bridgePayload.verified_at
                    ? ` · Establishment check reported: ${callUtc(bridgePayload.verified_at)}`
                    : ''}
                </p>
              )}
              {payload.established_at && (
                <p className="text-sm">
                  Direct establishment reported:{' '}
                  {callUtc(payload.established_at)}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Operator reports; these actions do not control hardware.
              </p>
              <div className="flex flex-wrap gap-2">
                {ongoing && onCallAction && (
                  <>
                    {connected.slice(1).map((customer) => (
                      <button
                        key={customer.record_id}
                        className={button}
                        disabled={disabled}
                        onClick={() => onCustomerAction?.(customer, 'left')}
                      >
                        {customerLeft(customer)}
                      </button>
                    ))}
                    {!connected.length &&
                      primary?.label !== 'Connect Customer' && (
                        <button
                          className={button}
                          disabled={disabled || incomplete || !ready}
                          onClick={() => onCallAction(r, 'connect')}
                        >
                          Connect Customer
                        </button>
                      )}
                    {r.time.occurred_at && primary?.label !== 'Finish Call' && (
                      <button
                        className={button}
                        disabled={disabled || !canFinish}
                        onClick={() => onCallAction(r, 'finish')}
                      >
                        Finish Call
                      </button>
                    )}
                    {!!connected.length && (
                      <p className="text-sm">
                        Report the customer leaving before finishing. The bridge
                        stays available for reuse.
                      </p>
                    )}
                    <button
                      className={button}
                      disabled={disabled || !!r.time.occurred_at}
                      onClick={() => onCallAction(r, 'cancel')}
                    >
                      Cancel Call
                    </button>
                  </>
                )}
                <button
                  className={button}
                  disabled={disabled || r.deleted}
                  onClick={() => onEdit(r)}
                >
                  {onCallAction && ongoing && !r.time.occurred_at
                    ? 'Reschedule'
                    : 'Edit Call'}
                </button>
                <button
                  className={button}
                  onClick={() => onHistory(r.record_id)}
                >
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
            </div>
          </details>
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
