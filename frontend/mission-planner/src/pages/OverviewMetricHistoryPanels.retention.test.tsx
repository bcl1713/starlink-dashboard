/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StatusResponse } from '../services/status';
import { OverviewMetricHistoryPanels } from './OverviewMetricHistoryPanels';

// Canvas is external to jsdom; exercise the real group and readout panels.
vi.mock('uplot', () => ({ default: class {} }));

function status(timestampSeconds: number, latencyMs: number): StatusResponse {
  return {
    timestamp: new Date(timestampSeconds * 1000).toISOString(),
    metric_availability: { latency_ms: true },
    network: { latency_ms: latencyMs },
  };
}

function group(
  observation: StatusResponse | undefined,
  nowMs = 109_000,
  statusError = false
) {
  return (
    <OverviewMetricHistoryPanels
      status={observation}
      statusError={statusError}
      history={undefined}
      error={false}
      selectedWindowSeconds={30}
      nowMs={nowMs}
    />
  );
}

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    }
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('OverviewMetricHistoryPanels skew-aware retention', () => {
  it('retains the newer skew-valid observation when an older one arrives', () => {
    const view = render(group(status(113, 7)));
    const panel = screen.getByLabelText('Network latency history');
    expect(panel.querySelector('strong')?.textContent).toBe('7 ms');
    expect(within(panel).getByText('Observed 00:01:53 UTC')).toBeTruthy();

    const older = status(112, 99);
    view.rerender(group(older));
    expect(panel.querySelector('strong')?.textContent).toBe('7 ms');
    expect(within(panel).getByText('Observed 00:01:53 UTC')).toBeTruthy();

    // Acquisition time remains authoritative at the ten-second stale boundary.
    view.rerender(group(older, 123_000));
    expect(panel.querySelector('strong')?.textContent).toBe('Unavailable');
    expect(
      within(panel).getByText('Last observed 7 ms · 10s old')
    ).toBeTruthy();
  });

  it('retains the skew-valid observation after an empty failed refresh', () => {
    const view = render(group(status(108, 3)));
    const panel = screen.getByLabelText('Network latency history');
    expect(panel.querySelector('strong')?.textContent).toBe('3 ms');

    view.rerender(group(status(113, 7)));
    expect(panel.querySelector('strong')?.textContent).toBe('7 ms');
    expect(within(panel).getByText('Observed 00:01:53 UTC')).toBeTruthy();

    view.rerender(group(undefined, 109_000, true));
    expect(panel.querySelector('strong')?.textContent).toBe('Unavailable');
    expect(within(panel).getByText('Last observed 7 ms · 0s old')).toBeTruthy();
    expect(screen.getByText('Status refresh unavailable')).toBeTruthy();

    view.rerender(group(undefined, 114_000, true));
    expect(within(panel).getByText('Last observed 7 ms · 1s old')).toBeTruthy();
  });
});
