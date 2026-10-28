import { useState } from 'react';
import { eventUtc } from './eventFormatting';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
export function OperatorEventFeed({
  events,
  onClose,
  onOpenSource,
}: {
  events: OperatorEventsState;
  onClose: () => void;
  onOpenSource?: (
    event: import('@/types/operatorEvents').OperationalEvent
  ) => void;
}) {
  const [history, setHistory] = useState(false);
  const items = (events.snapshot?.events ?? []).filter(
    (event) => history || event.active
  );
  return (
    <div className="min-h-0 space-y-4 overflow-y-auto overscroll-contain pr-1">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button
          className="min-h-11 rounded-md border px-3"
          disabled={events.refreshing}
          onClick={events.refresh}
        >
          Refresh Events
        </button>
        <label className="flex min-h-11 items-center gap-2">
          <input
            type="checkbox"
            checked={history}
            onChange={(event) => setHistory(event.target.checked)}
          />
          Recent History
        </label>
      </div>
      {events.failed && (
        <p role="status">
          Feed unavailable. Last-known events remain visible; current state is
          unknown.
        </p>
      )}
      {events.loading && <p>Loading events…</p>}
      {events.snapshot?.coverage !== 'available' && (
        <p className="text-sm text-muted-foreground">
          Optional model inputs:{' '}
          {Array.from(
            new Set(
              events.snapshot?.sources
                .filter(
                  (source) =>
                    source.freshness !== 'fresh' &&
                    source.freshness !== 'disabled'
                )
                .map((source) => source.reason)
                .filter(Boolean)
            )
          )
            .slice(0, 3)
            .join('; ') || 'Some model inputs are unavailable.'}
        </p>
      )}
      {events.acknowledgmentError && (
        <p role="status" className="text-sm text-amber-400">
          {events.acknowledgmentError}
        </p>
      )}
      {events.storageWarning && (
        <p role="status" className="text-sm text-amber-400">
          {events.storageWarning}
        </p>
      )}
      {(events.pendingAcknowledgment || events.blocked) && (
        <div className="space-y-2 rounded-md border p-3 text-sm">
          <p>
            {events.blocked
              ? 'Pending acknowledgment requires reconciliation with the current store.'
              : 'Acknowledgment pending confirmation.'}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className="min-h-11 rounded-md border px-3"
              disabled={events.acknowledging || events.blocked}
              onClick={() => {
                void events.retryAcknowledgment();
              }}
            >
              Retry acknowledgment
            </button>
            <button
              className="min-h-11 rounded-md border px-3"
              disabled={events.acknowledging}
              onClick={events.discardPending}
            >
              Dismiss request and refresh
            </button>
          </div>
        </div>
      )}
      {!items.length && !events.loading && (
        <p className="text-sm">
          No events recorded in this window. Unknown sources remain unknown.
        </p>
      )}
      <ol className="space-y-3">
        {items.map((event) => {
          const notification = event.notification;
          const sourceTarget =
            event.kind === 'issue_followup'
              ? '#operator-issues'
              : event.kind.startsWith('call_')
                ? '#operator-communications'
                : '#operator-communications';
          const sourceName =
            event.kind === 'issue_followup'
              ? 'Open Issues'
              : event.kind.startsWith('call_')
                ? 'Open Communications'
                : 'Open Communications';
          return (
            <li
              key={`${event.event_id}:${notification.generation}`}
              className={`min-w-0 space-y-2 break-words rounded-lg border p-3 [overflow-wrap:anywhere] ${event.protected_participation_ids.length ? 'border-amber-500/60' : ''}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs tracking-wide text-muted-foreground">
                  {event.provenance === 'operator_reported'
                    ? 'Operator Reported'
                    : event.provenance[0].toUpperCase() +
                      event.provenance.slice(1)}{' '}
                  ·{' '}
                  {event.active
                    ? {
                        upcoming: 'Upcoming',
                        active: 'Active',
                        overdue: 'Overdue',
                        inactive: 'Inactive',
                        unknown: 'Unknown',
                      }[event.state]
                    : 'History'}
                </span>
                {event.protected_participation_ids.length > 0 && (
                  <span className="text-xs font-semibold text-amber-400">
                    Active customer relevance
                  </span>
                )}
              </div>
              <p className="font-medium">{event.title}</p>
              <p className="text-sm">
                {eventUtc(event.due_at)}
                {event.end_at ? ` — ${eventUtc(event.end_at)}` : ''}
              </p>
              {event.provenance === 'modeled' && (
                <p className="text-xs text-muted-foreground">
                  {event.time_basis === 'live_route_eta'
                    ? 'Live Route ETA'
                    : event.time_basis === 'planned_utc'
                      ? 'Preflight Plan Zulu'
                      : event.time_basis === 'live_unavailable'
                        ? 'Live Timing Unavailable'
                        : 'Best current estimate'}{' '}
                  · {event.freshness}
                </p>
              )}
              {event.discrepancies.map((discrepancy) => (
                <p key={discrepancy} className="text-xs text-amber-400">
                  {discrepancy}
                </p>
              ))}
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <button
                  className="min-h-11 rounded-md border px-3 disabled:opacity-50"
                  disabled={
                    events.failed ||
                    events.blocked ||
                    events.acknowledging ||
                    !!events.pendingAcknowledgment ||
                    notification.acknowledged ||
                    notification.retired ||
                    !notification.acknowledgment_available ||
                    !notification.available ||
                    !event.active
                  }
                  onClick={() => {
                    void events.acknowledge(event);
                  }}
                >
                  {notification.acknowledged ? 'Acknowledged' : 'Acknowledge'}
                </button>
                <a
                  href={sourceTarget}
                  onClick={(click) => {
                    if (onOpenSource) {
                      click.preventDefault();
                      onOpenSource(event);
                    }
                    onClose();
                  }}
                  className="inline-flex min-h-11 items-center underline"
                >
                  {sourceName}
                </a>
              </div>
              {!notification.acknowledgment_available && event.active && (
                <p className="text-xs text-muted-foreground">
                  Model acknowledgment unavailable until source revisions can be
                  guarded.
                </p>
              )}
              {notification.reason && (
                <p className="text-xs text-muted-foreground">
                  {notification.reason}
                </p>
              )}
              <details className="text-xs text-muted-foreground">
                <summary className="min-h-9 cursor-pointer py-2">
                  Source Details
                </summary>
                <p>
                  Captured {eventUtc(event.source_captured_at)} · freshness{' '}
                  {event.freshness}
                </p>
                <p>
                  {event.planned_due_at && (
                    <>
                      Plan reference {eventUtc(event.planned_due_at)} —{' '}
                      {eventUtc(event.planned_end_at)}
                      <br />
                    </>
                  )}
                  Source {event.source_ref ?? 'unknown'} · revision{' '}
                  {event.source_revision ?? 'unknown'}
                </p>
              </details>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
