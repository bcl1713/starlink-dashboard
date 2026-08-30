import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MetricHistoryDisclosure } from './MetricHistoryDisclosure';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

const series: readonly TimeSeriesDefinition[] = [
  {
    key: 'latency',
    label: 'Latency',
    color: '#1769aa',
    unit: 'ms',
    display: 'signed',
  },
];

describe('MetricHistoryDisclosure', () => {
  it('starts closed and renders the chronological latest 300 rows when opened', () => {
    const rows: TimeSeriesRow[] = Array.from({ length: 301 }, (_, index) => ({
      timestamp: `2026-08-29T12:${String(index % 60).padStart(2, '0')}:00Z`,
      epochSeconds: index,
      values: [index],
    }));

    render(
      <MetricHistoryDisclosure
        rows={rows}
        series={series}
        caption="Latency history"
      />
    );

    const button = screen.getByRole('button', { name: 'History' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    fireEvent.click(button);

    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Latest 300 of 301 samples')).toBeVisible();
    const scroller = screen.getByRole('region', {
      name: 'Metric history table',
    });
    expect(scroller).toHaveClass('overflow-x-auto');
    expect(scroller).not.toHaveAttribute('tabIndex');
    expect(screen.getAllByRole('row')).toHaveLength(301);
    expect(screen.queryByText('0.0 ms')).not.toBeInTheDocument();
    expect(screen.getByText('300.0 ms')).toBeVisible();
  });

  it('does not add keyboard focus when the table is not truncated', () => {
    render(
      <MetricHistoryDisclosure rows={[]} series={series} caption="History" />
    );

    fireEvent.click(screen.getByRole('button', { name: 'History' }));

    expect(
      screen.getByRole('region', { name: 'Metric history table' })
    ).not.toHaveAttribute('tabIndex');
  });

  it('focuses the sole labelled scroller only when measured content overflows', async () => {
    let resizeCallback: ResizeObserverCallback | null = null;
    class MockResizeObserver {
      observe = vi.fn();
      disconnect = vi.fn();
      constructor(callback: ResizeObserverCallback) {
        resizeCallback = callback;
      }
    }
    vi.stubGlobal('ResizeObserver', MockResizeObserver);

    try {
      render(
        <MetricHistoryDisclosure
          rows={[
            {
              timestamp: '2026-08-29T12:00:00Z',
              epochSeconds: 1,
              values: [1],
            },
          ]}
          series={series}
          caption="Latency history"
        />
      );
      fireEvent.click(screen.getByRole('button', { name: 'History' }));
      const scroller = screen.getByRole('region', {
        name: 'Metric history table',
      });

      Object.defineProperty(scroller, 'clientWidth', {
        configurable: true,
        value: 500,
      });
      Object.defineProperty(scroller, 'scrollWidth', {
        configurable: true,
        value: 500,
      });
      act(() => resizeCallback?.([], {} as ResizeObserver));
      expect(scroller).not.toHaveAttribute('tabIndex');

      Object.defineProperty(scroller, 'scrollWidth', {
        configurable: true,
        value: 501,
      });
      act(() => resizeCallback?.([], {} as ResizeObserver));
      await waitFor(() => expect(scroller).toHaveAttribute('tabIndex', '0'));
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('reacts to content, series, and dimension changes in the scroller', async () => {
    let resizeCallback: ResizeObserverCallback | null = null;
    const observe = vi.fn();
    class MockResizeObserver {
      observe = observe;
      disconnect = vi.fn();
      constructor(callback: ResizeObserverCallback) {
        resizeCallback = callback;
      }
    }
    vi.stubGlobal('ResizeObserver', MockResizeObserver);

    try {
      const { rerender } = render(
        <MetricHistoryDisclosure
          rows={[row(1, [1])]}
          series={series}
          caption="Latency history"
        />
      );
      fireEvent.click(screen.getByRole('button', { name: 'History' }));
      const scroller = screen.getByRole('region', {
        name: 'Metric history table',
      });
      setWidths(scroller, 700, 700);
      act(() => resizeCallback?.([], {} as ResizeObserver));
      expect(scroller).not.toHaveAttribute('tabIndex');

      const widerSeries = [
        ...series,
        {
          key: 'jitter',
          label: 'Jitter',
          color: '#177a55',
          unit: 'ms',
          display: 'signed',
        },
      ] as const;
      rerender(
        <MetricHistoryDisclosure
          rows={[row(1, [1, 2]), row(2, [3, 4])]}
          series={widerSeries}
          caption="Latency history"
        />
      );
      expect(observe).toHaveBeenCalled();
      setWidths(scroller, 400, 900);
      act(() => resizeCallback?.([], {} as ResizeObserver));
      await waitFor(() => expect(scroller).toHaveAttribute('tabIndex', '0'));

      setWidths(scroller, 900, 900);
      act(() => resizeCallback?.([], {} as ResizeObserver));
      await waitFor(() => expect(scroller).not.toHaveAttribute('tabIndex'));
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it.each(['absent', 'constructor', 'observe', 'measurement'] as const)(
    'keeps the scroller usable when ResizeObserver %s is hostile',
    (hostility) => {
      if (hostility === 'absent') {
        vi.stubGlobal('ResizeObserver', undefined);
      } else if (hostility === 'constructor') {
        vi.stubGlobal(
          'ResizeObserver',
          class {
            constructor() {
              throw new Error('observer failed');
            }
          }
        );
      } else {
        class MockResizeObserver {
          static callback: ResizeObserverCallback | null = null;
          observe = vi.fn(() => {
            if (hostility === 'observe') throw new Error('observe failed');
          });
          disconnect = vi.fn();
          constructor(callback: ResizeObserverCallback) {
            MockResizeObserver.callback = callback;
          }
        }
        vi.stubGlobal('ResizeObserver', MockResizeObserver);
      }

      try {
        render(
          <MetricHistoryDisclosure
            rows={[row(1, [1])]}
            series={series}
            caption="Latency history"
          />
        );
        fireEvent.click(screen.getByRole('button', { name: 'History' }));
        const scroller = screen.getByRole('region', {
          name: 'Metric history table',
        });
        if (hostility === 'measurement') {
          Object.defineProperty(scroller, 'scrollWidth', {
            configurable: true,
            get() {
              throw new Error('measurement failed');
            },
          });
          Object.defineProperty(scroller, 'clientWidth', {
            configurable: true,
            value: 1,
          });
          const observer = ResizeObserver as unknown as {
            callback: ResizeObserverCallback | null;
          };
          act(() => observer.callback?.([], {} as ResizeObserver));
        }

        expect(screen.getByRole('table')).toBeVisible();
        expect(scroller).not.toHaveAttribute('tabIndex');
      } finally {
        vi.unstubAllGlobals();
      }
    }
  );
});

function row(epochSeconds: number, values: readonly number[]): TimeSeriesRow {
  return {
    timestamp: `2026-08-29T12:00:0${epochSeconds}Z`,
    epochSeconds,
    values,
  };
}

function setWidths(
  scroller: HTMLElement,
  clientWidth: number,
  scrollWidth: number
): void {
  Object.defineProperty(scroller, 'clientWidth', {
    configurable: true,
    value: clientWidth,
  });
  Object.defineProperty(scroller, 'scrollWidth', {
    configurable: true,
    value: scrollWidth,
  });
}
