import { useLayoutEffect, useMemo, useRef } from 'react';
import uPlot from 'uplot';

import type { TimeSeriesChartProps } from './metric-panel-types';

type UPlotInstance = uPlot;

const MIN_WIDTH = 240;
const MAX_WIDTH = 4096;
const MIN_HEIGHT = 160;
const MAX_HEIGHT = 800;

export function useUPlotChart(
  props: Pick<
    TimeSeriesChartProps,
    'accessibleName' | 'rows' | 'series' | 'yRange' | 'zeroBaseline'
  >
) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const plotRef = useRef<UPlotInstance | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const latestRows = useRef(props.rows);
  const lastRows = useRef<readonly unknown[] | null>(null);
  const lastSize = useRef<{ width: number; height: number } | null>(null);
  const seriesCount = props.series.length;

  useLayoutEffect(() => {
    latestRows.current = props.rows;
  }, [props.rows]);

  const options = useMemo<uPlot.Options>(
    () => ({
      width: MIN_WIDTH,
      height: MIN_HEIGHT,
      cursor: { show: false },
      legend: { show: false },
      scales: {
        x: { time: true },
        y: buildYScale(props.yRange, props.zeroBaseline),
      },
      axes: [{}, {}],
      series: [
        {},
        ...props.series.map((series) => ({
          label: series.label,
          stroke: series.color,
          spanGaps: false,
        })),
      ],
    }),
    [props.series, props.yRange, props.zeroBaseline]
  );

  useLayoutEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const readSize = () => readValidSize(host);
    const ensurePlot = () => {
      const size = readSize();
      if (size === null) return;
      if (plotRef.current === null) {
        try {
          plotRef.current = new uPlot(
            { ...options, width: size.width, height: size.height },
            toUPlotData(latestRows.current, seriesCount),
            host
          );
          lastRows.current = latestRows.current;
          lastSize.current = size;
          labelPlot(plotRef.current, props.accessibleName);
        } catch {
          plotRef.current = null;
        }
        return;
      }
      if (
        lastSize.current === null ||
        lastSize.current.width !== size.width ||
        lastSize.current.height !== size.height
      ) {
        try {
          plotRef.current.setSize(size);
          lastSize.current = size;
        } catch {
          destroyPlot(plotRef.current);
          plotRef.current = null;
        }
      }
    };

    let observer: ResizeObserver | null = null;
    try {
      observer = new ResizeObserver(() => ensurePlot());
      observerRef.current = observer;
      observer.observe(host);
    } catch {
      disconnectObserver(observer);
      observerRef.current = null;
    }
    ensurePlot();

    return () => {
      disconnectObserver(observerRef.current);
      observerRef.current = null;
      destroyPlot(plotRef.current);
      plotRef.current = null;
      lastRows.current = null;
      lastSize.current = null;
    };
  }, [options, props.accessibleName, seriesCount]);

  useLayoutEffect(() => {
    if (plotRef.current === null || lastRows.current === props.rows) return;
    try {
      plotRef.current.setData(toUPlotData(props.rows, seriesCount));
      lastRows.current = props.rows;
    } catch {
      destroyPlot(plotRef.current);
      plotRef.current = null;
    }
  }, [props.rows, seriesCount]);

  return hostRef;
}

function readValidSize(element: HTMLElement) {
  try {
    const rect = element.getBoundingClientRect();
    if (
      !Number.isFinite(rect.width) ||
      !Number.isFinite(rect.height) ||
      rect.width <= 0 ||
      rect.height <= 0
    ) {
      return null;
    }
    return {
      width: clamp(Math.round(rect.width), MIN_WIDTH, MAX_WIDTH),
      height: clamp(Math.round(rect.height), MIN_HEIGHT, MAX_HEIGHT),
    };
  } catch {
    return null;
  }
}

function toUPlotData(
  rows: readonly TimeSeriesChartProps['rows'][number][],
  seriesCount = rows[0]?.values.length ?? 0
) {
  const acceptedRows = rows.filter((row) => Number.isFinite(row.epochSeconds));
  return [
    acceptedRows.map((row) => row.epochSeconds),
    ...Array.from({ length: seriesCount }, (_, index) =>
      acceptedRows.map((row) => normalizeValue(row.values[index]))
    ),
  ] as uPlot.AlignedData;
}

function normalizeValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function labelPlot(plot: UPlotInstance, accessibleName: string): void {
  try {
    plot.root.setAttribute('role', 'img');
    plot.root.setAttribute('aria-label', accessibleName);
    for (const canvas of plot.root.querySelectorAll('canvas')) {
      canvas.setAttribute('aria-hidden', 'true');
    }
  } catch {
    // ignored
  }
}

function disconnectObserver(observer: ResizeObserver | null): void {
  try {
    observer?.disconnect();
  } catch {
    // ignored
  }
}

function destroyPlot(plot: UPlotInstance | null): void {
  try {
    plot?.destroy();
  } catch {
    // ignored
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function buildYScale(
  yRange: TimeSeriesChartProps['yRange'],
  zeroBaseline: boolean
): uPlot.Scale {
  if (yRange !== 'auto') {
    const [min, max] = yRange;
    return { range: () => [min, max] };
  }
  if (!zeroBaseline) return {};
  return {
    range: (_self, min, max) => [Math.min(0, min ?? 0), Math.max(0, max ?? 0)],
  };
}
