import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import type { UIEvent } from 'react';
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
  const following = useRef(true);
  const expectedScrollTop = useRef(0);
  const followContext = useRef<string | null>(null);
  const positionNow = useCallback(() => {
    const marker = nowMarker.current;
    const body = marker?.closest('.ws-timeline-body');
    if (!marker || !body) return;
    const bodyTop = body.getBoundingClientRect().top;
    const visibleHeight = Math.max(
      0,
      Math.min(body.clientHeight, window.innerHeight - bodyTop)
    );
    body.scrollTop +=
      marker.getBoundingClientRect().top - bodyTop - visibleHeight * 0.65;
    // Browser scroll events also fire after our own positioning.
    expectedScrollTop.current = body.scrollTop;
  }, []);
  const attachNowMarker = useCallback(
    (marker: HTMLLIElement | null) => {
      nowMarker.current = marker;
      if (following.current) positionNow();
    },
    [positionNow]
  );
  function onTimelineScroll(event: UIEvent<HTMLDivElement>) {
    if (Math.abs(event.currentTarget.scrollTop - expectedScrollTop.current) > 1)
      following.current = false;
  }
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!timeline?.failed) setMonotonicNow(performance.now());
    }, 1000);
    const media = globalThis.matchMedia?.('(max-width: 900px)');
    const resize = (event: MediaQueryListEvent) => {
      following.current = true;
      setNarrow(event.matches);
      setOpen(false);
    };
    const reposition = () => {
      if (following.current) positionNow();
    };
    media?.addEventListener('change', resize);
    window.addEventListener('resize', reposition);
    return () => {
      clearInterval(timer);
      media?.removeEventListener('change', resize);
      window.removeEventListener('resize', reposition);
    };
  }, [timeline?.failed, positionNow]);
  const snapshot = timeline?.snapshot;
  const elapsed = Math.max(
    0,
    monotonicNow - (timeline?.receivedAt ?? -Infinity)
  );
  const stale = !!timeline?.failed || elapsed >= 30000;
  const now = Date.parse(snapshot?.as_of ?? '') + Math.min(elapsed, 30000);
  useLayoutEffect(() => {
    const context = snapshot
      ? JSON.stringify([
          snapshot.mission_id,
          snapshot.store_id,
          snapshot.api_epoch,
          snapshot.source_mode,
          snapshot.simulation_run_id,
        ])
      : null;
    if (context !== followContext.current) {
      followContext.current = context;
      following.current = true;
    }
    if (following.current) positionNow();
  }, [now, snapshot, narrow, open, positionNow]);
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
          following.current = true;
          positionNow();
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
      nowMarker={attachNowMarker}
      onOpenSource={onOpenSource ? source : undefined}
    />
  );
  return (
    <section className="ws-timeline" aria-label="Mission timeline">
      {narrow ? (
        <Dialog
          open={open}
          onOpenChange={(nextOpen) => {
            if (nextOpen) following.current = true;
            setOpen(nextOpen);
          }}
        >
          <div
            className="ws-timeline-strip"
            aria-label="Compact Mission Chronology"
          >
            <DialogTrigger asChild>
              <button
                className="ws-timeline-launch ws-timeline-chip"
                aria-label="Open mission timeline"
                title={summary}
              >
                <strong>
                  Timeline ·{' '}
                  {Number.isFinite(now)
                    ? `${new Date(now).toISOString().slice(11, 16)} Zulu`
                    : 'Time Unknown'}
                </strong>
                <span>{summary}</span>
              </button>
            </DialogTrigger>
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
          <DialogContent className="ws-timeline-dialog">
            <div className="ws-timeline-dialog-header">
              <DialogTitle>Mission timeline</DialogTitle>
              <DialogDescription>
                Whole mission · times in Zulu
              </DialogDescription>
              {controls}
            </div>
            <div className="ws-timeline-body" onScroll={onTimelineScroll}>
              {!snapshot && (
                <p role="status" className="ws-meta">
                  {summary}
                </p>
              )}
              {contents}
            </div>
          </DialogContent>
        </Dialog>
      ) : (
        <>
          <div className="ws-timeline-header">
            <h2>Mission timeline</h2>
          </div>
          <p className="ws-meta">
            {snapshot ? 'Whole mission · Zulu' : summary}
          </p>
          {controls}
          <div className="ws-timeline-body" onScroll={onTimelineScroll}>
            {contents}
          </div>
        </>
      )}
    </section>
  );
}
