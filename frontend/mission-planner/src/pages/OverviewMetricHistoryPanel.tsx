import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import type { OverviewHistoryBundle } from '../services/overview-history';
import { motionOffsetPixels } from './overview-metric-motion';
import {
  retainMetricHistory,
  type RetainedMetricHistory,
} from './overview-metric-retention';
import {
  projectMetricTraces,
  type OverviewMetricGraphDescriptor,
} from './overview-metric-history';
import { metricScale, type YRange } from './overview-metric-scale';
import { metricPlotOptions } from './overview-metric-plot-options';
import type { MetricReadout } from './overview-metric-readout';
import { formatMetricAxis, formatMetricValue } from './overview-metric-format';
import './OverviewMetricHistoryPanel.css';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';

const BUFFER_SECONDS = 7.5;

interface Props {
  descriptor: OverviewMetricGraphDescriptor;
  history: OverviewHistoryBundle | undefined;
  error: boolean;
  selectedWindowSeconds: number;
  nowMs: number;
  readout?: MetricReadout | null;
}

/** A plot-only uPlot canvas: labels and axes never enter the moving surface. */
export function OverviewMetricHistoryPanel({
  descriptor,
  history,
  error,
  selectedWindowSeconds,
  nowMs,
  readout,
}: Props) {
  const reducedMotion = usePrefersReducedMotion();
  const accepted = useRef<{
    windowSeconds: number;
    history: OverviewHistoryBundle | undefined;
    chart: RetainedMetricHistory | undefined;
  }>({
    windowSeconds: selectedWindowSeconds,
    history: undefined,
    chart: undefined,
  });
  if (accepted.current.windowSeconds !== selectedWindowSeconds)
    accepted.current = {
      windowSeconds: selectedWindowSeconds,
      history: undefined,
      chart: undefined,
    };
  const incomingHistory =
    history?.window_seconds === selectedWindowSeconds ? history : undefined;
  if (
    incomingHistory &&
    incomingHistory !== accepted.current.history &&
    (!accepted.current.history ||
      incomingHistory.end_timestamp_seconds >=
        accepted.current.history.end_timestamp_seconds)
  ) {
    accepted.current.chart = retainMetricHistory(
      accepted.current.chart,
      incomingHistory,
      descriptor
    );
    accepted.current.history = incomingHistory;
  }
  const validHistory = accepted.current.history;
  const retainedBundle = accepted.current.chart?.bundle;
  const projection = useMemo(
    () =>
      retainedBundle
        ? projectMetricTraces(retainedBundle, descriptor)
        : undefined,
    [retainedBundle, descriptor]
  );
  const viewport = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const paintedInput = useRef<{
    history: OverviewHistoryBundle;
    descriptor: OverviewMetricGraphDescriptor;
    width: number;
    height: number;
  } | null>(null);
  const [width, setWidth] = useState(0);
  const [height, setHeight] = useState(80);
  const [tick, setTick] = useState(0);
  const [hidden, setHidden] = useState(
    () => typeof document !== 'undefined' && document.hidden
  );
  const clockAnchor = useRef({
    windowSeconds: selectedWindowSeconds,
    bundleEnd: validHistory?.end_timestamp_seconds,
    nowMs,
    monotonicMs: performance.now(),
    effectiveMs: nowMs,
  });
  const monotonicMs = performance.now();
  // The compositor and performance.now() share a monotonic domain. Ignore
  // wall-clock jumps within one bundle: moving UTC labels to nowMs would run
  // ahead of the still-transitioning canvas. Re-anchor only on fresh data or
  // a selected-window change (which also rebases the plot surface).
  if (
    clockAnchor.current.windowSeconds !== selectedWindowSeconds ||
    clockAnchor.current.bundleEnd !== validHistory?.end_timestamp_seconds
  )
    clockAnchor.current = {
      windowSeconds: selectedWindowSeconds,
      bundleEnd: validHistory?.end_timestamp_seconds,
      nowMs,
      monotonicMs,
      effectiveMs: nowMs,
    };
  clockAnchor.current.effectiveMs = Math.max(
    clockAnchor.current.effectiveMs,
    clockAnchor.current.nowMs +
      Math.max(0, monotonicMs - clockAnchor.current.monotonicMs)
  );
  const currentSeconds = clockAnchor.current.effectiveMs / 1000;
  // Carry the visible time edge, not the new bundle's elapsed clock, across
  // rebases. When a poll arrives after overscan is exhausted the old surface
  // has stopped; resetting from nowMs would teleport retained samples.
  const scroll = useRef({
    windowSeconds: selectedWindowSeconds,
    end: validHistory?.end_timestamp_seconds,
    startedMs: monotonicMs,
    initialElapsed: validHistory
      ? Math.min(
          BUFFER_SECONDS,
          currentSeconds - validHistory.end_timestamp_seconds
        )
      : 0,
  });
  if (scroll.current.windowSeconds !== selectedWindowSeconds || !validHistory) {
    scroll.current = {
      windowSeconds: selectedWindowSeconds,
      end: validHistory?.end_timestamp_seconds,
      startedMs: monotonicMs,
      initialElapsed: validHistory
        ? Math.min(
            BUFFER_SECONDS,
            currentSeconds - validHistory.end_timestamp_seconds
          )
        : 0,
    };
  } else if (scroll.current.end !== validHistory.end_timestamp_seconds) {
    const previous = scroll.current;
    scroll.current = {
      windowSeconds: selectedWindowSeconds,
      end: validHistory.end_timestamp_seconds,
      startedMs: monotonicMs,
      initialElapsed:
        Math.min(
          BUFFER_SECONDS,
          previous.initialElapsed +
            Math.max(0, monotonicMs - previous.startedMs) / 1000
        ) +
        (previous.end ?? validHistory.end_timestamp_seconds) -
        validHistory.end_timestamp_seconds,
    };
  }
  const scrollElapsed = Math.min(
    BUFFER_SECONDS,
    scroll.current.initialElapsed +
      Math.max(0, monotonicMs - scroll.current.startedMs) / 1000
  );
  const elapsed = validHistory
    ? currentSeconds - validHistory.end_timestamp_seconds
    : 0;
  const frozen = useRef<{ key: string; elapsed: number } | null>(null);
  const freezeKey = `${descriptor.metric}/${validHistory?.end_timestamp_seconds}/${selectedWindowSeconds}`;
  if (error || hidden) {
    if (frozen.current?.key !== freezeKey)
      frozen.current = { key: freezeKey, elapsed: scrollElapsed };
  } else if (frozen.current) {
    if (frozen.current.key === freezeKey) {
      scroll.current.initialElapsed = frozen.current.elapsed;
      scroll.current.startedMs = monotonicMs;
    }
    frozen.current = null;
  }
  const motionElapsed = Math.min(
    BUFFER_SECONDS,
    frozen.current?.elapsed ??
      scroll.current.initialElapsed +
        Math.max(0, monotonicMs - scroll.current.startedMs) / 1000
  );
  // The bundle can be current while this metric's last real sample is old.
  // Projected times end in a real observed/rollup sample, never a gap marker.
  const sampleEnd = projection?.times.at(-1);
  const exhausted =
    !!validHistory &&
    (elapsed >= BUFFER_SECONDS ||
      nowMs / 1000 - validHistory.end_timestamp_seconds >= BUFFER_SECONDS ||
      (sampleEnd !== undefined &&
        (currentSeconds - sampleEnd >= BUFFER_SECONDS ||
          nowMs / 1000 - sampleEnd >= BUFFER_SECONDS)));
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
        projection.max,
        projection.min,
        projection.avg,
        projection.observed,
      ] as uPlot.AlignedData)
    : undefined;
  const scale = useRef<{ key: string; range: YRange } | null>(null);
  const scaleKey = `${descriptor.metric}/${selectedWindowSeconds}`;
  const yRange = useMemo(
    () =>
      metricScale(
        descriptor,
        projection,
        scale.current?.key === scaleKey ? scale.current.range : undefined
      ),
    [descriptor, projection, scaleKey]
  );
  scale.current = { key: scaleKey, range: yRange };
  const upper = yRange.max;
  const visibleRight = domain
    ? domain.max - BUFFER_SECONDS * 2 + Math.min(BUFFER_SECONDS, motionElapsed)
    : 0;
  const utcTime = (seconds: number) =>
    new Date(seconds * 1000).toISOString().slice(11, 19) + ' UTC';

  useEffect(() => {
    const node = viewport.current;
    if (!node) return;
    const measure = () => {
      setWidth(Math.max(0, node.clientWidth));
      setHeight(Math.max(1, node.clientHeight));
    };
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
    const offset = -(motionElapsed / windowSeconds) * width;
    node.style.transition = 'none';
    node.style.transform = `translate3d(${offset}px, 0, 0)`;
    if (!plot.current) {
      plot.current = new uPlot(
        metricPlotOptions({ width: overscanWidth, height, yRange, descriptor }),
        data,
        host.current
      );
    } else if (
      paintedInput.current?.history !== validHistory ||
      paintedInput.current?.descriptor !== descriptor ||
      paintedInput.current?.width !== width ||
      paintedInput.current?.height !== height
    ) {
      // Visibility/error changes only rebase motion; unchanged data need no upload.
      plot.current.setSize({ width: overscanWidth, height });
      plot.current.setData(data);
    }
    paintedInput.current = {
      history: validHistory!,
      descriptor,
      width,
      height,
    };
    plot.current.setScale('x', domain);
    plot.current.setScale('y', yRange);
    // Flush the rebase before changing the transition endpoint.
    node.getBoundingClientRect();
    const remaining = Math.max(0, BUFFER_SECONDS - motionElapsed);
    const timer = window.setTimeout(() => {
      if (!hidden && !error && !reducedMotion && remaining > 0) {
        node.style.transition = `transform ${remaining}s linear`;
        node.style.transform = `translate3d(${motionOffsetPixels({ elapsedSeconds: BUFFER_SECONDS, widthPixels: width, windowSeconds, bufferSeconds: BUFFER_SECONDS })}px, 0, 0)`;
      }
    }, 0);
    return () => window.clearTimeout(timer);
    // Deliberately exclude the status tick: CSS owns intermediate frames.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    validHistory,
    descriptor,
    width,
    height,
    hidden,
    error,
    selectedWindowSeconds,
    reducedMotion,
  ]);

  const status = !validHistory
    ? error
      ? 'History unavailable'
      : 'Waiting for history'
    : error
      ? 'Last-known history; refresh unavailable'
      : projection?.state === 'unavailable'
        ? 'Five-minute aggregates unavailable'
        : projection?.state === 'empty'
          ? 'Waiting for history samples'
          : exhausted
            ? 'Waiting for fresh history'
            : '';
  void tick;
  return (
    <section
      className="overview-metric-history"
      aria-label={`${descriptor.label} history`}
    >
      <header className="overview-metric-history__header">
        <h3>{descriptor.displayLabel ?? descriptor.label}</h3>
      </header>
      <strong
        className="overview-metric-history__latest"
        title={readout ? `${readout.value} ${descriptor.unit}` : undefined}
      >
        {readout?.state === 'fresh'
          ? formatMetricValue(readout.value, descriptor.unit)
          : 'Unavailable'}
      </strong>
      <div className="overview-metric-history__messages">
        <span
          className={`overview-metric-history__age${readout?.state === 'stale' ? '' : ' overview-visually-hidden'}`}
        >
          {readout?.state === 'stale'
            ? `Last observed ${formatMetricValue(readout.value, descriptor.unit)} · ${Math.floor(readout.ageMs / 1000)}s old`
            : readout
              ? `Observed ${new Date(readout.observedAtMs).toISOString().slice(11, 19)} UTC; exact value ${readout.value} ${descriptor.unit}`
              : 'No timestamped observation'}
        </span>
        {status && (
          <p
            className={`overview-metric-history__status${error ? ' overview-visually-hidden' : ''}`}
            role="status"
          >
            {status}
          </p>
        )}
      </div>
      <div className="overview-metric-history__chart">
        <div
          className="overview-metric-history__value-axis"
          aria-label={`${descriptor.unit} value axis`}
        >
          <span>{formatMetricAxis(upper)}</span>
          <span>{formatMetricAxis(upper / 2)}</span>
          <span>0</span>
        </div>
        <div
          className="overview-metric-history__viewport"
          ref={viewport}
          role="img"
          aria-label={`${descriptor.label} time history; ${descriptor.unit}; cyan observed, dashed five-minute average, shaded five-minute low–high range${status ? `; ${status}` : ''}`}
        >
          <div className="overview-metric-history__surface" ref={surface}>
            <div ref={host} />
          </div>
        </div>
      </div>
      <div className="overview-metric-history__time-axis overview-visually-hidden">
        <span>{domain ? utcTime(visibleRight - windowSeconds) : ''}</span>
        <span>Time (UTC)</span>
        <span>{domain ? utcTime(visibleRight) : ''}</span>
      </div>
    </section>
  );
}
