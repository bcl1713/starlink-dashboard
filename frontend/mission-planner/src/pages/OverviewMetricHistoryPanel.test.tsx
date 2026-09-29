/** @vitest-environment jsdom */
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { OverviewHistoryBundle } from '../services/overview-history';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import { OverviewMetricHistoryPanel } from './OverviewMetricHistoryPanel';

const plot = vi.hoisted(() => ({
  create: vi.fn(),
  setData: vi.fn(),
  setScale: vi.fn(),
  setSize: vi.fn(),
  destroy: vi.fn(),
}));
vi.mock('uplot', () => ({
  default: class {
    constructor(options: unknown, data: unknown, host: HTMLElement) {
      plot.create(options, data, host);
      host.append(document.createElement('canvas'));
    }
    setData = plot.setData;
    setScale = plot.setScale;
    setSize = plot.setSize;
    destroy = plot.destroy;
  },
}));
let resize: ResizeObserverCallback;
let measuredWidth = 400;
const observer = { observe: vi.fn(), disconnect: vi.fn() };
const descriptor = OVERVIEW_METRIC_GRAPHS[0];
function bundle(end = 120): OverviewHistoryBundle {
  return {
    window_seconds: 30,
    start_timestamp_seconds: end - 30,
    end_timestamp_seconds: end,
    step_seconds: 5,
    series: {
      [descriptor.metric]: [
        [end - 10, 5],
        [end, 7],
      ],
    },
    rolling_5m: {
      [descriptor.metric]: {
        state: 'available',
        min: [[end - 10, 3]],
        avg: [[end - 10, 4]],
        max: [[end - 10, 6]],
      },
    },
  };
}
function panel(
  history: OverviewHistoryBundle | null = bundle(),
  error = false,
  nowMs = 120_000
) {
  return (
    <OverviewMetricHistoryPanel
      descriptor={descriptor}
      history={history ?? undefined}
      error={error}
      selectedWindowSeconds={30}
      nowMs={nowMs}
    />
  );
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(120_000);
  vi.clearAllMocks();
  measuredWidth = 400;
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
    configurable: true,
    get: () => measuredWidth,
  });
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: ResizeObserverCallback) {
        resize = callback;
      }
      observe = observer.observe;
      disconnect = observer.disconnect;
    }
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('OverviewMetricHistoryPanel', () => {
  it('shows four named traces and fixed accessible title, unit and time axes', () => {
    const { container } = render(panel());
    for (const name of ['Observed', 'Low (5m)', 'Average (5m)', 'High (5m)'])
      expect(screen.getByText(name)).not.toBeNull();
    expect(screen.getByText('Network latency')).not.toBeNull();
    expect(screen.getByText('ms')).not.toBeNull();
    expect(screen.getByText('Time (UTC)')).not.toBeNull();
    expect(plot.create).toHaveBeenCalledTimes(1);
    const options = plot.create.mock.calls[0][0];
    expect(options.axes).toEqual([{ show: false }, { show: false }]);
    expect(
      options.series.slice(1).map((series: { label: string }) => series.label)
    ).toEqual(['Observed', 'Low (5m)', 'Average (5m)', 'High (5m)']);
    const surface = container.querySelector(
      '.overview-metric-history__surface'
    )!;
    expect(surface.contains(screen.getByText('Network latency'))).toBe(false);
    expect(surface.contains(screen.getAllByText('ms')[0])).toBe(false);
    expect(surface.contains(screen.getByText('Observed'))).toBe(false);
    expect(surface.contains(screen.getByText('Time (UTC)'))).toBe(false);
  });
  it('does not append a fabricated point at current time', () => {
    render(panel());
    expect(plot.create.mock.calls[0][1][0]).toEqual([110, 115, 120]);
    expect(plot.create.mock.calls[0][1][1]).toEqual([5, null, 7]);
  });
  it('updates one plot on fresh data, rebases with aligned x range, and cleans up', () => {
    const view = render(panel());
    vi.setSystemTime(125_000);
    view.rerender(panel(bundle(125), false, 125_000));
    expect(plot.create).toHaveBeenCalledTimes(1);
    expect(plot.setData).toHaveBeenCalledTimes(1);
    expect(plot.setScale).toHaveBeenCalledWith('x', { min: 87.5, max: 132.5 });
    expect(
      (
        view.container.querySelector(
          '.overview-metric-history__surface'
        ) as HTMLElement
      ).style.transform
    ).toContain('translate3d(0px');
    view.unmount();
    expect(plot.destroy).toHaveBeenCalledTimes(1);
    expect(observer.disconnect).toHaveBeenCalledTimes(1);
  });
  it('resizes the existing plot without remounting', () => {
    render(panel());
    measuredWidth = 500;
    act(() => resize([], {} as ResizeObserver));
    expect(plot.setSize).toHaveBeenCalled();
    expect(plot.create).toHaveBeenCalledTimes(1);
  });
  it('announces empty, unavailable aggregates and last-known fetch failure', () => {
    const view = render(panel(null));
    expect(screen.getByText(/waiting for history/i)).not.toBeNull();
    const missing = bundle();
    delete missing.rolling_5m;
    view.rerender(panel(missing));
    expect(
      screen.getByText(/five-minute aggregates unavailable/i)
    ).not.toBeNull();
    view.rerender(panel(bundle(), true));
    expect(screen.getByText(/last-known/i)).not.toBeNull();
    view.rerender(panel(bundle(120), false, 140_000));
    expect(screen.getByText(/waiting for fresh history/i)).not.toBeNull();
  });
  it('stops at the real sample edge on missed polls and resumes only on fresh data', () => {
    const view = render(panel());
    act(() => vi.advanceTimersByTime(10_000));
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    expect(surface.style.transform).toContain('translate3d(-100px');
    expect(screen.getByText(/waiting for fresh history/i)).not.toBeNull();
    expect(plot.setData).not.toHaveBeenCalled();
  });
  it('invalidates an old chart when the selected window changes', () => {
    const view = render(panel());
    view.rerender(
      <OverviewMetricHistoryPanel
        descriptor={descriptor}
        history={bundle()}
        error={false}
        selectedWindowSeconds={60}
        nowMs={120_000}
      />
    );
    expect(screen.getByText('Waiting for history')).not.toBeNull();
    expect(plot.destroy).toHaveBeenCalledTimes(1);
    expect(
      view.container.querySelector('.overview-metric-history__surface canvas')
    ).toBeNull();
  });
  it('keeps numeric value and UTC time ticks outside the translated surface', () => {
    const view = render(panel());
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    )!;
    expect(screen.getByText('0 ms')).not.toBeNull();
    expect(screen.getByText('8 ms')).not.toBeNull();
    expect(screen.getAllByText(/UTC/).length).toBeGreaterThan(1);
    expect(surface.contains(screen.getByText('8 ms'))).toBe(false);
  });
  it('freezes the time axis with the canvas when a fetch fails', () => {
    const view = render(panel());
    vi.setSystemTime(122_000);
    view.rerender(panel(bundle(), true, 122_000));
    const right = view.container.querySelector(
      '.overview-metric-history__time-axis span:last-child'
    )?.textContent;
    act(() => vi.advanceTimersByTime(4_000));
    view.rerender(panel(bundle(), true, 122_000));
    expect(
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent
    ).toBe(right);
  });
});
