import { useEffect, useId, useState } from 'react';
import type { MissionTimelineState } from '@/hooks/api/useMissionTimeline';
import type { OperationalEvent } from '@/types/operatorEvents';
import { eventUtc } from '../eventFormatting';

function relative(target: number, now: number) {
  const seconds = Math.max(0, Math.round((target - now) / 1000));
  if (seconds < 60) return 'less than 1 min';
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} min`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.ceil((seconds % 3600) / 60);
  return `${hours} hr${minutes ? ` ${minutes} min` : ''}`;
}

export function MissionTimeline({
  timeline,
  onOpenSource,
  onOpenAlerts,
}: {
  timeline?: MissionTimelineState;
  onOpenSource?: (event: OperationalEvent) => void;
  onOpenAlerts?: () => void;
}) {
  const bodyId = useId();
  const [expanded, setExpanded] = useState(
    () => !globalThis.matchMedia?.('(max-width: 900px)').matches
  );
  const [monotonicNow, setMonotonicNow] = useState(() => performance.now());
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!timeline?.failed) setMonotonicNow(performance.now());
    }, 1000);
    const media = globalThis.matchMedia?.('(max-width: 900px)');
    const resize = (event: MediaQueryListEvent) => setExpanded(!event.matches);
    media?.addEventListener('change', resize);
    return () => {
      clearInterval(timer);
      media?.removeEventListener('change', resize);
    };
  }, [timeline?.failed]);
  const snapshot = timeline?.snapshot;
  const elapsed = Math.max(
    0,
    monotonicNow - (timeline?.receivedAt ?? -Infinity)
  );
  const stale = !!timeline?.failed || elapsed >= 30000;
  const now = Date.parse(snapshot?.as_of ?? '') + Math.min(elapsed, 30000);
  const events = [...(snapshot?.events ?? [])].sort((a, b) => {
    const first = a.due_at ? Date.parse(a.due_at) : Infinity;
    const second = b.due_at ? Date.parse(b.due_at) : Infinity;
    return first - second || a.event_id.localeCompare(b.event_id);
  });
  const past = (event: OperationalEvent) =>
    event.state === 'inactive' ||
    (event.end_at != null && Date.parse(event.end_at) <= now);
  const active = (event: OperationalEvent) =>
    !past(event) && event.due_at != null && Date.parse(event.due_at) <= now;
  const pastEvents = events.filter(past);
  const current = [
    ...events.filter(active),
    ...events.filter((event) => !past(event) && !active(event)),
  ];
  function row(event: OperationalEvent) {
    const unavailable =
      event.time_basis === 'live_unavailable' || !event.due_at;
    const lastKnown = stale || event.freshness !== 'fresh';
    const started = active(event);
    const leg = snapshot?.legs.find((leg) => leg.leg_id === event.leg_id);
    const endLabel =
      event.kind === 'restriction'
        ? 'Expected recovery'
        : event.kind === 'pop_advisory'
          ? 'Expected window end'
          : 'Planned end';
    const endRelative =
      event.kind === 'restriction'
        ? 'Recovery in'
        : event.kind === 'pop_advisory'
          ? 'Window ends in'
          : 'Ends in';
    const label = unavailable
      ? 'Timing unavailable'
      : event.time_basis === 'live_route_eta'
        ? 'Live route ETA'
        : 'Scheduled';
    return (
      <li
        key={event.event_id}
        className="ws-timeline-row"
        data-active={started}
      >
        <h3>{event.title}</h3>
        {leg && <p className="ws-meta">{leg.name}</p>}
        <p className="ws-meta">
          {label}
          {lastKnown ? ' · Last known' : ''}
        </p>
        {!unavailable && (
          <>
            <p className="ws-meta">
              {event.kind === 'restriction' || event.kind === 'pop_advisory'
                ? 'Start '
                : ''}
              {eventUtc(event.due_at)}
            </p>
            {event.end_at && (
              <p className="ws-meta">
                {endLabel} {eventUtc(event.end_at)}
              </p>
            )}
            {!lastKnown && !past(event) && (
              <p className="ws-timeline-relative">
                {started && event.end_at
                  ? `${endRelative} ${relative(Date.parse(event.end_at), now)}`
                  : started
                    ? 'Due now / overdue'
                    : `In ${relative(Date.parse(event.due_at!), now)}`}
              </p>
            )}
          </>
        )}
        <details>
          <summary>Details</summary>
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
            <button className="ws-button" onClick={() => onOpenSource(event)}>
              Open source
            </button>
          )}
        </details>
      </li>
    );
  }
  return (
    <section className="ws-timeline" aria-label="Mission timeline">
      <div className="ws-timeline-header">
        <h2>Mission timeline</h2>
        {onOpenAlerts && (
          <button
            className="ws-button"
            onClick={onOpenAlerts}
            aria-label="Open operational alerts"
          >
            Alerts
          </button>
        )}
        <button
          className="ws-button ws-timeline-toggle"
          aria-label={
            expanded ? 'Collapse mission timeline' : 'Expand mission timeline'
          }
          aria-expanded={expanded}
          aria-controls={bodyId}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      </div>
      <p className="ws-meta">
        {snapshot
          ? `${current.length} current / upcoming · ${snapshot.legs.length} legs`
          : timeline?.loading
            ? 'Loading mission timeline…'
            : 'Mission timeline unavailable.'}
      </p>
      <div id={bodyId} hidden={!expanded} className="ws-timeline-body">
        {snapshot && stale && (
          <p role="status" className="ws-meta">
            Last known timeline · current timing unavailable. Refresh to resume
            countdowns.
          </p>
        )}
        {snapshot?.legs
          .filter((leg) => leg.coverage !== 'available')
          .map((leg) => (
            <p className="ws-meta" key={leg.leg_id}>
              {leg.name} · {leg.coverage.replace('_', ' ')}
              {leg.reason ? `: ${leg.reason}` : ''}
            </p>
          ))}
        {timeline && (
          <button
            className="ws-button"
            disabled={timeline.refreshing}
            onClick={timeline.refresh}
          >
            Refresh timeline
          </button>
        )}
        {snapshot && (
          <>
            <p className="ws-timeline-now">Now</p>
            <ol aria-label="Current and upcoming events">{current.map(row)}</ol>
            {!current.length && (
              <p className="ws-meta">No known current or upcoming events.</p>
            )}
            <details className="ws-timeline-past">
              <summary>Past · {pastEvents.length}</summary>
              <p className="ws-meta">
                Elapsed estimates, not observed outage history.
              </p>
              <ol aria-label="Past events">{pastEvents.map(row)}</ol>
            </details>
          </>
        )}
      </div>
    </section>
  );
}
