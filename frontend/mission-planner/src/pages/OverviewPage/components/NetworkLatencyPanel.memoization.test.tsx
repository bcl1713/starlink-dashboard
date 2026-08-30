import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NetworkLatencyPanel } from './NetworkLatencyPanel';
import { buildLatencyPanelData } from './metric-panel-data';
import { history, NOW, samples, slot } from './metric-panel-test-fixtures';
import { MockResizeObserver, createdPlots, resetUPlotMock } from './uplot.mock';

vi.mock('uplot', async () => ({
  default: (await import('./uplot.mock')).MockUPlot,
}));

vi.mock('./metric-panel-data', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./metric-panel-data')>();
  return {
    ...actual,
    buildLatencyPanelData: vi.fn(actual.buildLatencyPanelData),
  };
});

const metricHistory = history([
  {
    metric: 'latency_ms',
    samples: samples([['2026-08-29T12:30:00Z', 100]]),
  },
]);

beforeEach(() => {
  resetUPlotMock();
  vi.mocked(buildLatencyPanelData).mockClear();
  vi.stubGlobal('ResizeObserver', MockResizeObserver);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    width: 640,
    height: 240,
    x: 0,
    y: 0,
    top: 0,
    right: 640,
    bottom: 240,
    left: 0,
    toJSON: () => ({}),
  } as DOMRect);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('NetworkLatencyPanel memoized projection', () => {
  it('skips projection and setData for presentation, retry, heading, and slot wrapper rerenders', () => {
    const retry = vi.fn();
    const { rerender } = render(
      <NetworkLatencyPanel
        slot={slot(metricHistory)}
        now={NOW}
        retryPending={false}
        onRetry={retry}
      />
    );

    expect(buildLatencyPanelData).toHaveBeenCalledTimes(1);
    expect(createdPlots).toHaveLength(1);
    expect(createdPlots[0].setData).not.toHaveBeenCalled();

    rerender(
      <NetworkLatencyPanel
        slot={slot(metricHistory)}
        now={NOW}
        retryPending={false}
        onRetry={retry}
        presentation="compact"
      />
    );
    rerender(
      <NetworkLatencyPanel
        slot={slot(metricHistory)}
        now={NOW}
        retryPending
        onRetry={retry}
        presentation="compact"
      />
    );
    rerender(
      <NetworkLatencyPanel
        slot={slot(metricHistory)}
        now={NOW}
        retryPending
        onRetry={retry}
        presentation="compact"
        headingAs="h3"
      />
    );
    rerender(
      <NetworkLatencyPanel
        slot={{ ...slot(metricHistory) }}
        now={NOW}
        retryPending
        onRetry={retry}
        presentation="compact"
        headingAs="h3"
      />
    );

    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(
      'Network Latency'
    );
    expect(buildLatencyPanelData).toHaveBeenCalledTimes(1);
    expect(createdPlots[0].setData).not.toHaveBeenCalled();

    const nextHistory = history([
      {
        metric: 'latency_ms',
        samples: samples([['2026-08-29T12:30:01Z', 101]]),
      },
    ]);

    rerender(
      <NetworkLatencyPanel
        slot={slot(nextHistory)}
        now={NOW}
        retryPending
        onRetry={retry}
        presentation="compact"
        headingAs="h3"
      />
    );
    expect(buildLatencyPanelData).toHaveBeenCalledTimes(2);
    expect(createdPlots[0].setData).toHaveBeenCalledTimes(1);

    rerender(
      <NetworkLatencyPanel
        slot={slot(nextHistory)}
        now="2026-08-29T12:30:01Z"
        retryPending
        onRetry={retry}
        presentation="compact"
        headingAs="h3"
      />
    );
    expect(buildLatencyPanelData).toHaveBeenCalledTimes(3);
    expect(createdPlots[0].setData).toHaveBeenCalledTimes(2);
  });
});
