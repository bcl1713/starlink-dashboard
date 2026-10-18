import type { EventSnapshot, OperationalEvent } from '@/types/operatorEvents';
import type { SavedRecord } from '@/types/operator';
import { eventUtc } from '../eventFormatting';

function Timing({ event }: { event: OperationalEvent }) {
  if (event.time_basis === 'live_unavailable')
    return <span>Live timing unavailable</span>;
  return (
    <span>
      {event.time_basis === 'live_route_eta'
        ? 'Live ETA · '
        : event.time_basis === 'planned_utc'
          ? 'Planned · '
          : ''}
      {eventUtc(event.due_at)}
    </span>
  );
}

export function WorkspaceAwareness({
  snapshot,
  next,
  records,
  recordsIncomplete,
  failed,
  onOpenRecord,
  onOpenEvents,
}: {
  snapshot?: EventSnapshot;
  next?: OperationalEvent;
  records: SavedRecord[];
  recordsIncomplete: boolean;
  failed: boolean;
  onOpenRecord?: (record: SavedRecord) => void;
  onOpenEvents?: () => void;
}) {
  const customers = records.filter(
    (record) =>
      !record.deleted &&
      record.payload.entry_type === 'participation' &&
      record.payload.state === 'connected'
  );
  const events = snapshot?.events.filter((event) => event.active) ?? [];
  const attention = events.filter(
    (event) => event.state === 'overdue' || event.state === 'unknown'
  );
  const advisories = events.filter(
    (event) => event.kind === 'restriction' || event.kind === 'pop_advisory'
  );
  const prep = next
    ? events.find(
        (event) =>
          event.kind === 'call_prep' && event.source_ref === next.source_ref
      )
    : undefined;
  return (
    <section className="ws-awareness" aria-label="Now and next">
      <section className="ws-now" aria-label="Reported connected customers">
        <h2>Now</h2>
        <p className="ws-meta">
          Reported connected · {customers.length}
          {recordsIncomplete ? ' loaded' : ''}
        </p>
        {customers.length ? (
          <ul className="ws-customers">
            {customers.map((record) => (
              <li key={record.record_id}>
                <button
                  className="ws-customer"
                  onClick={() => onOpenRecord?.(record)}
                >
                  <span className="ws-connected-dot" aria-hidden="true" />
                  <span>
                    {record.payload.entry_type === 'participation'
                      ? record.payload.participant ||
                        record.payload.title ||
                        'Unnamed customer'
                      : record.payload.title}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="ws-meta">No reported connected customers.</p>
        )}
      </section>
      <section className="ws-next" aria-label="Next requirement">
        <h2>Next requirement</h2>
        {next ? (
          <>
            <p className="ws-next-name">{next.title}</p>
            <p className="ws-meta">
              <Timing event={next} />
            </p>
            {prep && (
              <p className="ws-meta">
                Prepare · <Timing event={prep} />
              </p>
            )}
          </>
        ) : (
          <p className="ws-meta">
            {!snapshot || failed
              ? 'Next requirement unavailable.'
              : 'No timed future requirement recorded.'}
          </p>
        )}
      </section>
      <details className="ws-attention">
        <summary>
          Attention · {attention.length}
          {snapshot?.truncated ? ' loaded' : ''}
        </summary>
        <ul>
          {attention.map((event) => (
            <li key={event.event_id}>
              <p>{event.title}</p>
              <p className="ws-meta">
                {event.state} · <Timing event={event} />
              </p>
            </li>
          ))}
        </ul>
        {!attention.length && (
          <p className="ws-meta">No loaded overdue or unknown-time events.</p>
        )}
      </details>
      <details className="ws-advisories">
        <summary>
          Advisories · {advisories.length}
          {snapshot?.truncated ? ' loaded' : ''}
        </summary>
        <ul>
          {advisories.map((event) => (
            <li key={event.event_id}>
              <p>{event.title}</p>
              <p className="ws-meta">
                <Timing event={event} /> · {event.freshness}
              </p>
            </li>
          ))}
        </ul>
        <p className="ws-meta">
          Transition windows are advisories; they do not establish a service
          outage.
        </p>
      </details>
      <div className="ws-coverage">
        {failed && (
          <p role="status">Feed unavailable · last known information.</p>
        )}
        <p className="ws-meta">
          Coverage {snapshot?.coverage ?? 'unknown'}
          {snapshot?.truncated ? ' · event pages incomplete' : ''}
        </p>
        {recordsIncomplete && (
          <p className="ws-meta">
            Loaded records only · more records may be available.
          </p>
        )}
        <details>
          <summary>Source status</summary>
          <p className="ws-meta">Snapshot {eventUtc(snapshot?.as_of)}</p>
          {snapshot?.sources.map((source) => (
            <p className="ws-meta" key={source.source}>
              {source.source} · {source.freshness} ·{' '}
              {source.aligned ? 'aligned' : 'not aligned'}
              {source.reason ? ` · ${source.reason}` : ''}
            </p>
          ))}
        </details>
        {onOpenEvents && (
          <button className="ws-button" onClick={onOpenEvents}>
            Open timeline
          </button>
        )}
      </div>
    </section>
  );
}
