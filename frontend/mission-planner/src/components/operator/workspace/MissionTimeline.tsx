import { useEffect, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import type { MissionTimelineState } from '@/hooks/api/useMissionTimeline';
import type { OperationalEvent } from '@/types/operatorEvents';
import { MissionTimelineContents } from './MissionTimelineContents';
import { timelineTime } from '../eventFormatting';

export function MissionTimeline({
  timeline,
  onOpenSource,
  onOpenAlerts,
}: {
  timeline?: MissionTimelineState;
  onOpenSource?: (event: OperationalEvent) => void;
  onOpenAlerts?: () => void;
}) {
  const [narrow, setNarrow] = useState(
    () => !!globalThis.matchMedia?.('(max-width: 900px)').matches
  );
  const [open, setOpen] = useState(false);
  const [monotonicNow, setMonotonicNow] = useState(() => performance.now());
  const nowMarker = useRef<HTMLLIElement>(null);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!timeline?.failed) setMonotonicNow(performance.now());
    }, 1000);
    const media = globalThis.matchMedia?.('(max-width: 900px)');
    const resize = (event: MediaQueryListEvent) => {
      setNarrow(event.matches);
      setOpen(false);
    };
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
  const next = [...(snapshot?.events ?? [])]
    .filter(
      (event) =>
        event.state !== 'inactive' &&
        event.due_at &&
        Date.parse(event.due_at) > now
    )
    .sort((a, b) => Date.parse(a.due_at!) - Date.parse(b.due_at!))[0];
  const summary = snapshot
    ? stale
      ? 'Last known timeline'
      : next
        ? `${next.freshness === 'fresh' ? 'Next' : 'Last known'} ${timelineTime(next.due_at!, snapshot.as_of)} · ${next.title}`
        : `${snapshot.events.length} events · ${snapshot.legs.length} legs`
    : timeline?.loading
      ? 'Loading mission timeline…'
      : 'Mission timeline unavailable.';
  function source(event: OperationalEvent) {
    setOpen(false);
    onOpenSource?.(event);
  }
  const controls = (
    <div className="ws-timeline-controls">
      <button
        className="ws-button"
        onClick={() => {
          const marker = nowMarker.current;
          const body = marker?.closest('.ws-timeline-body');
          if (marker && body) {
            const bodyTop = body.getBoundingClientRect().top;
            const visibleHeight = Math.max(
              0,
              Math.min(body.clientHeight, window.innerHeight - bodyTop)
            );
            body.scrollTop +=
              marker.getBoundingClientRect().top -
              bodyTop -
              visibleHeight * 0.65;
          }
        }}
      >
        Jump to now
      </button>
      {timeline && (
        <button
          className="ws-button"
          disabled={timeline.refreshing}
          onClick={timeline.refresh}
        >
          Refresh timeline
        </button>
      )}
      {onOpenAlerts && (
        <button
          className="ws-button"
          onClick={() => {
            setOpen(false);
            onOpenAlerts();
          }}
          aria-label="Open operational alerts"
        >
          Alerts
        </button>
      )}
    </div>
  );
  const contents = (
    <MissionTimelineContents
      snapshot={snapshot}
      now={now}
      stale={stale}
      nowMarker={nowMarker}
      onOpenSource={onOpenSource ? source : undefined}
    />
  );
  return (
    <section className="ws-timeline" aria-label="Mission timeline">
      {narrow ? (
        <>
          <div
            className="ws-timeline-strip"
            aria-label="Compact Mission Chronology"
          >
            <span className="ws-timeline-strip-now">
              Now
              {Number.isFinite(now)
                ? ` · ${new Date(now).toISOString().slice(11, 16)} Zulu`
                : ' · Unknown'}
            </span>
            {snapshot?.events
              .filter(
                (event) =>
                  event.active &&
                  (!event.end_at || Date.parse(event.end_at) >= now)
              )
              .slice(0, 8)
              .map((event) => (
                <button
                  key={event.event_id}
                  className="ws-timeline-chip"
                  aria-label={`Focus ${event.title}`}
                  onClick={() => source(event)}
                  disabled={!onOpenSource}
                >
                  <strong>{event.title}</strong>
                  <span>
                    {event.due_at
                      ? timelineTime(event.due_at, snapshot.as_of)
                      : 'Timing Unknown'}
                    {stale || event.freshness !== 'fresh'
                      ? ' · Last Known'
                      : ''}
                  </span>
                </button>
              ))}
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <button
                className="ws-timeline-launch ws-button"
                aria-label="Open mission timeline"
              >
                <span>
                  <strong>Mission timeline</strong>
                  <span className="ws-meta">{summary}</span>
                </span>
                <span aria-hidden="true">View all →</span>
              </button>
            </DialogTrigger>
            <DialogContent className="ws-timeline-dialog">
              <div className="ws-timeline-dialog-header">
                <DialogTitle>Mission timeline</DialogTitle>
                <DialogDescription>
                  Whole mission · times in Zulu
                </DialogDescription>
                {controls}
              </div>
              <div className="ws-timeline-body">
                {!snapshot && (
                  <p role="status" className="ws-meta">
                    {summary}
                  </p>
                )}
                {contents}
              </div>
            </DialogContent>
          </Dialog>
        </>
      ) : (
        <>
          <div className="ws-timeline-header">
            <h2>Mission timeline</h2>
          </div>
          <p className="ws-meta">
            {snapshot ? 'Whole mission · Zulu' : summary}
          </p>
          {controls}
          <div className="ws-timeline-body">{contents}</div>
        </>
      )}
    </section>
  );
}
