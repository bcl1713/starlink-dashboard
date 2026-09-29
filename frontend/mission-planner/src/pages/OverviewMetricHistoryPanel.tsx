import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { OverviewHistoryBundle } from '../services/overview-history';
import { motionOffsetPixels } from './overview-metric-motion';
import {
  projectMetricHistory,
  type OverviewMetricGraphDescriptor,
} from './overview-metric-history';
import './OverviewMetricHistoryPanel.css';

const BUFFER_SECONDS = 7.5;
const HEIGHT = 80;
const TRACES = [
  { label: 'Observed', stroke: '#67e8f9' },
  { label: 'Low (5m)', stroke: '#a78bfa' },
  { label: 'Average (5m)', stroke: '#fbbf24' },
  { label: 'High (5m)', stroke: '#fb7185' },
] as const;

interface Props {
  descriptor: OverviewMetricGraphDescriptor;
  history: OverviewHistoryBundle | undefined;
  error: boolean;
  selectedWindowSeconds: number;
  nowMs: number;
}

/** A plot-only uPlot canvas: labels and axes never enter the moving surface. */
export function OverviewMetricHistoryPanel({
  descriptor,
  history,
  error,
  selectedWindowSeconds,
  nowMs,
}: Props) {
  const accepted = useRef<{
    windowSeconds: number;
    history: OverviewHistoryBundle | undefined;
  }>({ windowSeconds: selectedWindowSeconds, history: undefined });
  if (accepted.current.windowSeconds !== selectedWindowSeconds)
    accepted.current = {
      windowSeconds: selectedWindowSeconds,
      history: undefined,
    };
  const incomingHistory =
    history?.window_seconds === selectedWindowSeconds ? history : undefined;
  if (
    incomingHistory &&
    (!accepted.current.history ||
      incomingHistory.end_timestamp_seconds >=
        accepted.current.history.end_timestamp_seconds)
  )
    accepted.current.history = incomingHistory;
  const validHistory = incomingHistory ? accepted.current.history : undefined;
  const projection = validHistory
    ? projectMetricHistory(validHistory, descriptor, nowMs)
    : undefined;
  const viewport = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const [width, setWidth] = useState(0);
  const [tick, setTick] = useState(0);
  const [hidden, setHidden] = useState(
    () => typeof document !== 'undefined' && document.hidden
  );
  const clockAnchor = useRef({
    windowSeconds: selectedWindowSeconds,
    nowMs,
    monotonicMs: performance.now(),
    effectiveMs: nowMs,
  });
  const monotonicMs = performance.now();
  // CSS transitions and performance.now() share the browser's monotonic time
  // domain. A wall-clock or nowMs rewind cannot stall the ticks while the
  // compositor continues; only a selected-window change resets the timeline.
  if (clockAnchor.current.windowSeconds !== selectedWindowSeconds)
    clockAnchor.current = {
      windowSeconds: selectedWindowSeconds,
      nowMs,
      monotonicMs,
      effectiveMs: nowMs,
    };
  const effectiveMs = Math.max(
    clockAnchor.current.effectiveMs,
    clockAnchor.current.nowMs +
      Math.max(0, monotonicMs - clockAnchor.current.monotonicMs)
  );
  if (nowMs > effectiveMs)
    clockAnchor.current = {
      windowSeconds: selectedWindowSeconds,
      nowMs,
      monotonicMs,
      effectiveMs: nowMs,
    };
  else clockAnchor.current.effectiveMs = effectiveMs;
  const currentSeconds = clockAnchor.current.effectiveMs / 1000;
  const elapsed = validHistory
    ? currentSeconds - validHistory.end_timestamp_seconds
    : 0;
  const frozen = useRef<{ key: string; elapsed: number } | null>(null);
  const freezeKey = `${descriptor.metric}/${validHistory?.end_timestamp_seconds}/${selectedWindowSeconds}`;
  if (error || hidden) {
    if (frozen.current?.key !== freezeKey)
      frozen.current = { key: freezeKey, elapsed };
  } else frozen.current = null;
  const motionElapsed = frozen.current?.elapsed ?? elapsed;
  const exhausted = !!validHistory && elapsed >= BUFFER_SECONDS;
  const windowSeconds = selectedWindowSeconds > 0 ? selectedWindowSeconds : 1;
  const overscanWidth = Math.max(
    1,
    Math.round(width * (1 + (2 * BUFFER_SECONDS) / windowSeconds))
  );
  const domain = validHistory
    ? {
        min:
          validHistory.end_timestamp_seconds - windowSeconds - BUFFER_SECONDS,
        max: validHistory.end_timestamp_seconds + BUFFER_SECONDS,
      }
    : undefined;
  const data = projection
    ? ([
        projection.times,
        projection.observed,
        projection.min,
        projection.avg,
        projection.max,
      ] as uPlot.AlignedData)
    : undefined;
  const maximum = projection
    ? [projection.observed, projection.min, projection.avg, projection.max]
        .flat()
        .reduce<number>(
          (peak, value) =>
            typeof value === 'number' && Number.isFinite(value)
              ? Math.max(peak, value)
              : peak,
          1
        )
    : 1;
  const upper = Math.ceil(maximum * 1.1);
  const visibleRight = domain
    ? domain.max -
      BUFFER_SECONDS * 2 +
      Math.min(BUFFER_SECONDS, Math.max(0, motionElapsed))
    : 0;
  const utcTime = (seconds: number) =>
    new Date(seconds * 1000).toISOString().slice(11, 19) + ' UTC';

  useEffect(() => {
    const node = viewport.current;
    if (!node) return;
    const measure = () => setWidth(Math.max(0, node.clientWidth));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const onVisibility = () => setHidden(document.hidden);
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);
  useEffect(() => {
    if (!validHistory || hidden) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 250);
    return () => window.clearInterval(timer);
  }, [validHistory, hidden]);
  useEffect(
    () => () => {
      plot.current?.destroy();
      plot.current = null;
    },
    []
  );

  useLayoutEffect(() => {
    if (!domain || !data) {
      plot.current?.destroy();
      plot.current = null;
      host.current?.replaceChildren();
      return;
    }
    if (!host.current || !surface.current || !width) return;
    const node = surface.current;
    // A fresh bundle changes the plot origin, but the old and new transforms
    // place the same timestamp at the same screen coordinate. Cancel the old
    // transition before rebasing; start a new linear compositor transition.
    const offset = motionOffsetPixels({
      elapsedSeconds: motionElapsed,
      widthPixels: width,
      windowSeconds,
      bufferSeconds: BUFFER_SECONDS,
    });
    node.style.transition = 'none';
    node.style.transform = `translate3d(${offset}px, 0, 0)`;
    if (!plot.current) {
      plot.current = new uPlot(
        {
          width: overscanWidth,
          height: HEIGHT,
          padding: [0, 0, 0, 0],
          axes: [{ show: false }, { show: false }],
          legend: { show: false },
          cursor: { show: false },
          scales: {
            x: { time: true, range: [domain.min, domain.max] },
            y: { range: [0, upper] },
          },
          series: [
            {},
            ...TRACES.map((trace) => ({
              ...trace,
              width: 1.5,
              spanGaps: false,
            })),
          ],
        },
        data,
        host.current
      );
    } else {
      plot.current.setSize({ width: overscanWidth, height: HEIGHT });
      plot.current.setData(data);
      plot.current.setScale('x', domain);
      plot.current.setScale('y', { min: 0, max: upper });
    }
    // Flush the rebase before changing the transition endpoint.
    node.getBoundingClientRect();
    const remaining = Math.max(0, BUFFER_SECONDS - Math.max(0, motionElapsed));
    const timer = window.setTimeout(() => {
      if (!hidden && !error && remaining > 0) {
        node.style.transition = `transform ${remaining}s linear`;
        node.style.transform = `translate3d(${motionOffsetPixels({ elapsedSeconds: BUFFER_SECONDS, widthPixels: width, windowSeconds, bufferSeconds: BUFFER_SECONDS })}px, 0, 0)`;
      }
    }, 0);
    return () => window.clearTimeout(timer);
    // Deliberately exclude the status tick: CSS owns intermediate frames.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validHistory, descriptor, width, hidden, error, selectedWindowSeconds]);

  const status = !validHistory
    ? 'Waiting for history'
    : error
      ? 'Last-known history; refresh unavailable'
      : projection?.state === 'unavailable'
        ? 'Five-minute aggregates unavailable'
        : projection?.state === 'empty'
          ? 'Waiting for history samples'
          : exhausted
            ? 'Waiting for fresh history'
            : 'History available';
  void tick;
  return (
    <section
      className="overview-metric-history"
      aria-label={`${descriptor.label} history`}
    >
      <header className="overview-metric-history__header">
        <h3>{descriptor.label}</h3>
        <span className="overview-metric-history__unit">{descriptor.unit}</span>
      </header>
      <p className="overview-metric-history__status" role="status">
        {status}
      </p>
      <ul className="overview-metric-history__legend" aria-label="Graph traces">
        {TRACES.map((trace) => (
          <li key={trace.label}>
            <span
              style={{ backgroundColor: trace.stroke }}
              aria-hidden="true"
            />
            {trace.label}
          </li>
        ))}
      </ul>
      <div className="overview-metric-history__chart">
        <div
          className="overview-metric-history__value-axis"
          aria-label={`${descriptor.unit} value axis`}
        >
          <span>
            {upper} {descriptor.unit}
          </span>
          <span>0 {descriptor.unit}</span>
        </div>
        <div
          className="overview-metric-history__viewport"
          ref={viewport}
          role="img"
          aria-label={`${descriptor.label} time history; ${status}`}
        >
          <div className="overview-metric-history__surface" ref={surface}>
            <div ref={host} />
          </div>
        </div>
      </div>
      <div className="overview-metric-history__time-axis">
        <span>{domain ? utcTime(visibleRight - windowSeconds) : ''}</span>
        <span>Time (UTC)</span>
        <span>{domain ? utcTime(visibleRight) : ''}</span>
      </div>
    </section>
  );
}
