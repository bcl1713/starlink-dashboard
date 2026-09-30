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
  it('keeps the accessible title, unit and time axes outside the plot without a duplicate legend', () => {
    const { container } = render(panel());
    expect(screen.queryByLabelText('Graph traces')).toBeNull();
    expect(screen.getByText('Network latency')).not.toBeNull();
    expect(screen.getByText('ms')).not.toBeNull();
    expect(screen.getByText('Time (UTC)')).not.toBeNull();
    expect(plot.create).toHaveBeenCalledTimes(1);
    const options = plot.create.mock.calls[0][0];
    expect(options.axes).toEqual([{ show: false }, { show: false }]);
    expect(
      options.series.slice(1).map((series: { label: string }) => series.label)
    ).toEqual(['High', 'Low', 'Average', 'Observed']);
    const surface = container.querySelector(
      '.overview-metric-history__surface'
    )!;
    expect(surface.contains(screen.getByText('Network latency'))).toBe(false);
    expect(surface.contains(screen.getAllByText('ms')[0])).toBe(false);
    expect(surface.contains(screen.getByText('Unavailable'))).toBe(false);
    expect(surface.contains(screen.getByText('Time (UTC)'))).toBe(false);
  });
  it('does not append a fabricated point at current time', () => {
    render(panel());
    expect(plot.create.mock.calls[0][1][0]).toEqual([110, 115, 120]);
    expect(plot.create.mock.calls[0][1][4]).toEqual([5, null, 7]);
  });
  it('updates one plot on fresh data, rebases with aligned x range, and cleans up', () => {
    const view = render(panel());
    act(() => vi.advanceTimersByTime(5_000));
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
  it('caps an initially stale canvas at the same edge as its UTC ticks', () => {
    vi.setSystemTime(140_000);
    const view = render(panel(bundle(120), false, 140_000));
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    expect(surface.style.transform).toContain('translate3d(-100px');
    expect(
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent
    ).toBe('00:02:00 UTC');
    act(() => vi.advanceTimersByTime(0));
    expect(surface.style.transition).toBe('none');
  });
  it('keeps UTC ticks aligned with the canvas when nowMs reverses', () => {
    vi.setSystemTime(125_000);
    const history = bundle(120);
    const view = render(panel(history, false, 125_000));
    const right = () =>
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent;
    const surface = () =>
      view.container.querySelector(
        '.overview-metric-history__surface'
      ) as HTMLElement;
    expect(right()).toBe('00:01:57 UTC');
    const transform = surface().style.transform;
    vi.setSystemTime(121_000);
    view.rerender(panel(history, false, 121_000));
    expect(right()).toBe('00:01:57 UTC');
    expect(surface().style.transform).toBe(transform);
    expect(plot.setScale).toHaveBeenCalledTimes(2);
    expect(plot.setScale).toHaveBeenCalledWith('x', {
      min: 82.5,
      max: 127.5,
    });
  });
  it('advances fixed UTC ticks with the continuing CSS transition after both clocks rewind', () => {
    vi.setSystemTime(125_000);
    const history = bundle(120);
    const view = render(panel(history, false, 125_000));
    const right = () =>
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent;
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    const start = Number(
      surface.style.transform.match(/translate3d\(([-\d.]+)px/)?.[1]
    );
    expect(start).toBeCloseTo(-400 * (5 / 30));
    act(() => vi.advanceTimersByTime(0));
    expect(surface.style.transition).toBe('transform 2.5s linear');
    vi.setSystemTime(121_000);
    view.rerender(panel(history, false, 121_000));
    act(() => vi.advanceTimersByTime(2_000));
    // jsdom has no compositor. At 2/2.5 of the linear transition, its
    // interpolated offset is -400 * (7/30); the fixed tick must name that edge.
    const interpolatedOffset =
      start +
      ((Number(surface.style.transform.match(/translate3d\(([-\d.]+)px/)?.[1]) -
        start) *
        2) /
        2.5;
    expect(interpolatedOffset).toBeCloseTo(-400 * (7 / 30));
    expect(right()).toBe('00:01:59 UTC');
  });
  it('keeps UTC ticks on the CSS edge after a forward nowMs jump', () => {
    vi.setSystemTime(125_000);
    const history = bundle(120);
    const view = render(panel(history, false, 125_000));
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    const right = () =>
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent;
    act(() => vi.advanceTimersByTime(0));
    expect(surface.style.transition).toBe('transform 2.5s linear');
    act(() => vi.advanceTimersByTime(500));
    view.rerender(panel(history, false, 140_000));
    // The compositor has moved half a second, not the 15 seconds of a wall-clock jump.
    expect(right()).toBe('00:01:58 UTC');
    expect(surface.style.transition).toBe('transform 2.5s linear');
  });
  it('ignores an older same-window bundle then accepts a newer recovery', () => {
    const view = render(panel(bundle(120), false, 125_000));
    const right = () =>
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent;
    const surface = () =>
      view.container.querySelector(
        '.overview-metric-history__surface'
      ) as HTMLElement;
    const transform = surface().style.transform;
    view.rerender(panel(bundle(115), false, 125_000));
    expect(right()).toBe('00:01:57 UTC');
    expect(surface().style.transform).toBe(transform);
    expect(plot.setData).not.toHaveBeenCalled();
    view.rerender(panel(bundle(130), false, 130_000));
    // A late recovery preserves the retained timestamp's screen position.
    expect(right()).toBe('00:01:57 UTC');
    expect(plot.setData).toHaveBeenCalledTimes(1);
    expect(plot.setScale).toHaveBeenCalledWith('x', { min: 92.5, max: 137.5 });
  });
  it('expands both canvas and fixed axis for a delayed real spike without remounting', () => {
    const view = render(panel());
    const next = bundle(125);
    next.series[descriptor.metric] = [[125, 23]];
    view.rerender(panel(next, false, 130_000));
    expect(plot.setScale).toHaveBeenLastCalledWith('y', { min: 0, max: 26 });
    expect(screen.getByText('26 ms')).not.toBeNull();
    expect(plot.create).toHaveBeenCalledTimes(1);
    const lower = bundle(130);
    lower.series[descriptor.metric] = [[130, 21]];
    view.rerender(panel(lower, false, 130_000));
    expect(screen.getByText('26 ms')).not.toBeNull();
    expect(plot.setScale).toHaveBeenLastCalledWith('y', { min: 0, max: 26 });
  });

  it('labels the packet-loss upper axis explicitly at one percent for small samples', () => {
    const loss = OVERVIEW_METRIC_GRAPHS[3];
    const history = bundle();
    history.series[loss.metric] = [[120, 0.2]];
    history.rolling_5m![loss.metric] = {
      state: 'available',
      min: [[120, 0]],
      avg: [[120, 0.1]],
      max: [[120, 0.2]],
    };
    render(
      <OverviewMetricHistoryPanel
        descriptor={loss}
        history={history}
        error={false}
        selectedWindowSeconds={30}
        nowMs={120_000}
      />
    );
    expect(screen.getByText('1 %')).not.toBeNull();
    expect(screen.getByText('0 %')).not.toBeNull();
    expect(plot.setScale).toHaveBeenLastCalledWith('y', { min: 0, max: 1 });
  });

  it('renders a readable fractional loss label agreeing exactly with the canvas domain', () => {
    const loss = OVERVIEW_METRIC_GRAPHS[3];
    const history = bundle();
    history.series[loss.metric] = [[120, 1.2]];
    render(
      <OverviewMetricHistoryPanel
        descriptor={loss}
        history={history}
        error={false}
        selectedWindowSeconds={30}
        nowMs={120_000}
      />
    );
    expect(screen.getByText('1.4 %')).not.toBeNull();
    expect(plot.setScale).toHaveBeenLastCalledWith('y', { min: 0, max: 1.4 });
  });
  // These probes catch an incorrect x-domain/transform rebase, viewport-based
  // speed, or per-tick data upload. Canvas/compositor paint is covered in E2E.
  it.each([1, 5])(
    'preserves all four series positions at %ss bundle rebases',
    (interval) => {
      const history = (end: number) => {
        const next = bundle(end);
        next.series[descriptor.metric] = [
          [110, 5],
          [end, 7],
        ];
        next.rolling_5m![descriptor.metric] = {
          state: 'available',
          min: [[110, 3]],
          avg: [[110, 4]],
          max: [[110, 6]],
        };
        return next;
      };
      const view = render(panel(history(120)));
      const surface = view.container.querySelector(
        '.overview-metric-history__surface'
      ) as HTMLElement;
      for (const end of [120 + interval, 120 + 2 * interval]) {
        act(() => vi.advanceTimersByTime(interval * 1000));
        // The old CSS transition is linear; derive its position independently.
        const before =
          ((110 - (120 - 37.5)) / 45) * 600 - ((end - 120) / 30) * 400;
        view.rerender(panel(history(end), false, end * 1000));
        const domain = plot.setScale.mock.calls
          .filter(([axis]) => axis === 'x')
          .at(-1)![1];
        const offset = Number(
          surface.style.transform.match(/translate3d\(([-\d.]+)px/)?.[1]
        );
        const after =
          ((110 - domain.min) / (domain.max - domain.min)) * 600 + offset;
        const data = plot.setData.mock.calls.at(-1)![0];
        const marker = data[0].indexOf(110);
        expect(data.slice(1).map((column: number[]) => column[marker])).toEqual(
          [6, 3, 4, 5]
        );
        for (const column of data.slice(1)) {
          expect(column[marker]).not.toBeNull();
          expect(Math.abs(after - before)).toBeLessThanOrEqual(1);
        }
      }
      expect(plot.setData).toHaveBeenCalledTimes(2);
      act(() => vi.advanceTimersByTime(8_000));
      expect(plot.setData).toHaveBeenCalledTimes(2);
    }
  );
  it('recalculates motion and uPlot size from a 400 to 300 CSS-pixel viewport', () => {
    const view = render(panel());
    act(() => vi.advanceTimersByTime(2_000));
    measuredWidth = 300;
    act(() => resize([], {} as ResizeObserver));
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    expect(plot.setSize).toHaveBeenLastCalledWith({ width: 450, height: 1 });
    expect(surface.style.transform).toBe('translate3d(-20px, 0, 0)');
    act(() => vi.advanceTimersByTime(0));
    expect(surface.style.transition).toBe('transform 5.5s linear');
    expect(surface.style.transform).toBe('translate3d(-75px, 0, 0)');
    expect(plot.setData).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(8_000));
    expect(plot.setData).toHaveBeenCalledTimes(1);
    expect(plot.create).toHaveBeenCalledTimes(1);
  });
  it('caps an eight-second delayed poll without extrapolating samples', () => {
    const view = render(panel());
    act(() => vi.advanceTimersByTime(8_000));
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    expect(surface.style.transform).toBe('translate3d(-100px, 0, 0)');
    expect(screen.getByRole('status').textContent).toBe(
      'Waiting for fresh history'
    );
    expect(plot.setData).not.toHaveBeenCalled();
    view.rerender(panel(bundle(128), false, 128_000));
    expect(plot.setData).toHaveBeenCalledTimes(1);
    expect(plot.setData.mock.calls[0][0][0].at(-1)).toBe(128);
    expect(surface.style.transform).toContain(
      'translate3d(6.666666666666667px'
    );
  });
  it('resumes from the frozen edge without replaying missed transitions', () => {
    const history = bundle();
    const view = render(panel(history));
    act(() => vi.advanceTimersByTime(2_000));
    const surface = view.container.querySelector(
      '.overview-metric-history__surface'
    ) as HTMLElement;
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      value: true,
    });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    const frozen = surface.style.transform;
    act(() => vi.advanceTimersByTime(120_000));
    expect(surface.style.transform).toBe(frozen);
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      value: false,
    });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(surface.style.transform).toBe(frozen);
    act(() => vi.advanceTimersByTime(0));
    expect(surface.style.transition).toBe('transform 5.5s linear');
    expect(plot.create).toHaveBeenCalledTimes(1);
    expect(plot.setData).not.toHaveBeenCalled();
  });
  it('marks an initial failed fetch unavailable without claiming last-known data', () => {
    const view = render(panel(null, true));
    expect(screen.getByRole('status').textContent).toBe('History unavailable');
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain(
      'History unavailable'
    );
    expect(plot.create).not.toHaveBeenCalled();
    view.rerender(panel(bundle(), false));
    expect(screen.queryByRole('status')).toBeNull();
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
  it('marks old-only metric samples stale even when the query bundle is fresh', () => {
    const old = bundle(120);
    old.series[descriptor.metric] = [[95, 0]];
    old.rolling_5m![descriptor.metric] = {
      state: 'available',
      min: [[105, 0]],
      avg: [[105, 0]],
      max: [[105, 0]],
    };
    const view = render(panel(old));
    expect(screen.getByRole('status').textContent).toBe(
      'Waiting for fresh history'
    );
    expect(plot.create.mock.calls[0][1][0]).toEqual([95, 100, 105]);
    expect(plot.create.mock.calls[0][1][4]).toEqual([0, null, null]);
    const fresh = bundle(125);
    fresh.series[descriptor.metric] = [[125, 0]];
    view.rerender(panel(fresh, false, 125_000));
    expect(screen.queryByRole('status')).toBeNull();
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
  it('keeps unavailable aggregate and empty states ahead of sample staleness', () => {
    const missing = bundle();
    missing.series[descriptor.metric] = [[90, 0]];
    delete missing.rolling_5m;
    const view = render(panel(missing));
    expect(screen.getByRole('status').textContent).toBe(
      'Five-minute aggregates unavailable'
    );
    const empty = bundle();
    empty.series[descriptor.metric] = [];
    empty.rolling_5m![descriptor.metric] = {
      state: 'available',
      min: [],
      avg: [],
      max: [],
    };
    view.rerender(panel(empty));
    expect(screen.getByRole('status').textContent).toBe(
      'Waiting for history samples'
    );
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
  it('does not present a previous window as last-known after a failed new-window fetch', () => {
    const view = render(panel());
    view.rerender(
      <OverviewMetricHistoryPanel
        descriptor={descriptor}
        history={bundle()}
        error={true}
        selectedWindowSeconds={60}
        nowMs={120_000}
      />
    );
    expect(screen.getByRole('status').textContent).toBe('History unavailable');
    expect(plot.destroy).toHaveBeenCalledTimes(1);
  });
  it('accepts a valid bundle for a newly selected window', () => {
    const view = render(panel(bundle(120), false, 125_000));
    const next = { ...bundle(100), window_seconds: 60 };
    view.rerender(
      <OverviewMetricHistoryPanel
        descriptor={descriptor}
        history={next}
        error={false}
        selectedWindowSeconds={60}
        nowMs={100_000}
      />
    );
    expect(screen.queryByText('Waiting for history')).toBeNull();
    expect(plot.setScale).toHaveBeenCalledWith('x', {
      min: 32.5,
      max: 107.5,
    });
    expect(
      view.container.querySelector(
        '.overview-metric-history__time-axis span:last-child'
      )?.textContent
    ).toBe('00:01:32 UTC');
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
