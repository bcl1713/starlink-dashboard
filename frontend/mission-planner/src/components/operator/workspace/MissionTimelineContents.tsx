import type { RefObject } from 'react';
import type { MissionTimelineSnapshot } from '@/types/missionTimeline';
import type { OperationalEvent } from '@/types/operatorEvents';
import { eventUtc, timelineTime } from '../eventFormatting';
function relative(target: number, now: number) {
  const minutes = Math.max(1, Math.ceil((target - now) / 60000));
  return minutes < 60
    ? `${minutes} min`
    : `${Math.floor(minutes / 60)} hr${minutes % 60 ? ` ${minutes % 60} min` : ''}`;
}
interface Entry {
  id: string;
  at: string | null;
  title: string;
  leg?: string;
  event?: OperationalEvent;
  lastKnown?: boolean;
}

export function MissionTimelineContents({
  snapshot,
  now,
  stale,
  nowMarker,
  onOpenSource,
}: {
  snapshot?: MissionTimelineSnapshot;
  now: number;
  stale: boolean;
  nowMarker: RefObject<HTMLLIElement | null>;
  onOpenSource?: (event: OperationalEvent) => void;
}) {
  const entries: Entry[] = (snapshot?.events ?? []).map((event) => ({
    id: event.event_id,
    at: event.due_at,
    title: event.title,
    leg: snapshot?.legs.find((leg) => leg.leg_id === event.leg_id)?.name,
    event,
  }));
  for (const leg of snapshot?.legs ?? []) {
    if (leg.scheduled_departure_at)
      entries.push({
        id: `departure:${leg.leg_id}`,
        at: leg.scheduled_departure_at,
        title: 'Scheduled departure',
        leg: leg.name,
        lastKnown: leg.coverage === 'last_known',
      });
    if (leg.scheduled_arrival_at)
      entries.push({
        id: `arrival:${leg.leg_id}`,
        at: leg.scheduled_arrival_at,
        title: 'Scheduled arrival',
        leg: leg.name,
        lastKnown: leg.coverage === 'last_known',
      });
    if (
      !leg.scheduled_departure_at &&
      !leg.scheduled_arrival_at &&
      (leg.coverage === 'unavailable' || leg.coverage === 'last_known')
    )
      entries.push({
        id: `unavailable:${leg.leg_id}`,
        at: null,
        title: 'Route timing unavailable',
        leg: leg.name,
        lastKnown: leg.coverage === 'last_known',
      });
  }
  entries.sort(
    (a, b) =>
      (a.at ? Date.parse(a.at) : Infinity) -
        (b.at ? Date.parse(b.at) : Infinity) || a.id.localeCompare(b.id)
  );
  const nowIndex = entries.findIndex(
    (entry) => !entry.at || Date.parse(entry.at) > now
  );
  const marker = (
    <li className="ws-timeline-now" ref={nowMarker} key="now">
      Now
      {Number.isFinite(now)
        ? ` · ${eventUtc(new Date(now).toISOString()).slice(0, 16)} UTC`
        : ''}
    </li>
  );
  const row = (entry: Entry) => {
    const event = entry.event;
    const elapsed =
      event &&
      ((event.state === 'inactive' &&
        !!event.due_at &&
        Date.parse(event.due_at) <= now) ||
        (!!event.end_at && Date.parse(event.end_at) <= now));
    const started =
      event?.due_at &&
      Date.parse(event.due_at) <= now &&
      !elapsed &&
      event.state !== 'inactive';
    const lastKnown =
      stale || entry.lastKnown || (event && event.freshness !== 'fresh');
    const unavailable = event?.time_basis === 'live_unavailable' || !entry.at;
    const label = unavailable
      ? 'Timing unavailable'
      : !event
        ? 'Route schedule'
        : event.time_basis === 'live_route_eta'
          ? 'Live route ETA'
          : event.kind === 'restriction' || event.kind === 'pop_advisory'
            ? 'Scheduled route time'
            : 'Fixed time';
    const endLabel =
      event?.kind === 'restriction'
        ? 'Expected recovery'
        : event?.kind === 'pop_advisory'
          ? 'Expected window end'
          : 'Planned end';
    const endRelative =
      event?.kind === 'restriction'
        ? 'Recovery in'
        : event?.kind === 'pop_advisory'
          ? 'Window ends in'
          : 'Ends in';
    return (
      <li
        key={entry.id}
        className="ws-timeline-row"
        data-active={!!started}
        data-elapsed={!!elapsed}
      >
        <div className="ws-timeline-time">
          {entry.at ? (
            <time dateTime={entry.at} title={eventUtc(entry.at)}>
              {timelineTime(entry.at)}
            </time>
          ) : (
            '—'
          )}
        </div>
        <div className="ws-timeline-event">
          <h3>{entry.title}</h3>
          {entry.leg && <p className="ws-meta">{entry.leg}</p>}
          <p className="ws-meta">
            {label}
            {lastKnown ? ' · Last known' : ''}
          </p>
          {event?.end_at && !unavailable && (
            <p className="ws-meta">
              {endLabel}{' '}
              <time dateTime={event.end_at} title={eventUtc(event.end_at)}>
                {timelineTime(event.end_at, entry.at)}
              </time>
            </p>
          )}
          {elapsed ? (
            <p className="ws-meta">
              {event.kind === 'restriction' || event.kind === 'pop_advisory'
                ? 'Elapsed estimate'
                : 'Past scheduled time'}
            </p>
          ) : event?.state === 'inactive' ? (
            <p className="ws-meta">Inactive</p>
          ) : (
            event &&
            !unavailable &&
            !lastKnown && (
              <p className="ws-timeline-relative">
                {started && event.end_at
                  ? `${endRelative} ${relative(Date.parse(event.end_at), now)}`
                  : started
                    ? 'Due now / overdue'
                    : `In ${relative(Date.parse(event.due_at!), now)}`}
              </p>
            )
          )}
          {event && (
            <details>
              <summary>Details</summary>
              {event.due_at && (
                <p className="ws-meta">{eventUtc(event.due_at)}</p>
              )}
              {event.planned_due_at && (
                <p className="ws-meta">
                  Schedule reference: {eventUtc(event.planned_due_at)}
                  {event.planned_end_at
                    ? ` to ${eventUtc(event.planned_end_at)}`
                    : ''}
                </p>
              )}
              <p className="ws-meta">
                {event.confidence ?? 'Mission estimate'} · {event.freshness}
              </p>
              {event.source_captured_at && (
                <p className="ws-meta">
                  Source captured {eventUtc(event.source_captured_at)}
                </p>
              )}
              {event.kind === 'pop_advisory' && (
                <p className="ws-meta">
                  Transition advisory; does not establish a service outage.
                </p>
              )}
              {onOpenSource && (
                <button
                  className="ws-button"
                  onClick={() => onOpenSource(event)}
                >
                  Open source
                </button>
              )}
            </details>
          )}
        </div>
      </li>
    );
  };
  return (
    <>
      {snapshot && stale && (
        <p role="status" className="ws-meta">
          Last known timeline · current timing unavailable. Refresh to resume
          countdowns.
        </p>
      )}
      {snapshot && (
        <>
          <ol aria-label="Mission events from start to finish">
            {entries.map((entry, index) => {
              const date = entry.at?.slice(0, 10) ?? 'Time not determined';
              const newDay =
                index === 0 ||
                date !==
                  (entries[index - 1].at?.slice(0, 10) ??
                    'Time not determined');
              return [
                index === nowIndex && marker,
                newDay && (
                  <li key={`date:${date}`} className="ws-timeline-date">
                    {date} {entry.at ? 'UTC' : ''}
                  </li>
                ),
                row(entry),
              ];
            })}
            {nowIndex < 0 && marker}
          </ol>
          {!entries.length && (
            <p className="ws-meta">No known mission events.</p>
          )}
          <details className="ws-timeline-sources">
            <summary>Source status</summary>
            <p className="ws-meta">
              Elapsed windows are estimates, not observed outage history.
            </p>
            {snapshot.legs
              .filter((leg) => leg.coverage !== 'available')
              .map((leg) => (
                <p className="ws-meta" key={leg.leg_id}>
                  {leg.name} · {leg.coverage.replace('_', ' ')}
                  {leg.reason ? `: ${leg.reason}` : ''}
                </p>
              ))}
          </details>
        </>
      )}
    </>
  );
}
