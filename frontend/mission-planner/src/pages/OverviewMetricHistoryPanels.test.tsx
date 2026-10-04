/** @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StatusResponse } from '../services/status';
import type { OverviewHistoryBundle } from '../services/overview-history';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import { OverviewMetricHistoryPanels } from './OverviewMetricHistoryPanels';

const subscriptions = vi.hoisted(() => ({ status: vi.fn(), history: vi.fn() }));
vi.mock('../hooks/api/useStatus', () => ({ useStatus: subscriptions.status }));
vi.mock('../hooks/api/useOverviewHistory', () => ({
  useOverviewHistory: subscriptions.history,
}));
const plot = vi.hoisted(() => ({ create: vi.fn(), setData: vi.fn() }));
// Canvas is external to jsdom; keep the real panels, projection and lifecycle.
vi.mock('uplot', () => ({
  default: class {
    constructor(options: unknown, data: unknown) {
      plot.create(options, data);
    }
    setData = plot.setData;
    setScale() {}
    setSize() {}
    destroy() {}
  },
}));
function statusFixture(): StatusResponse {
  return {
    timestamp: '1970-01-01T00:01:45.000Z',
    metric_availability: {
      latency_ms: true,
      throughput_down_mbps: true,
      throughput_up_mbps: true,
      packet_loss_percent: true,
      obstruction_percent: true,
    },
    network: {
      latency_ms: 7,
      throughput_down_mbps: 0,
      throughput_up_mbps: 2,
      packet_loss_percent: 0.2,
    },
    obstruction: { obstruction_percent: 3 },
  };
}
function bundle(end = 105): OverviewHistoryBundle {
  return {
    window_seconds: 30,
    start_timestamp_seconds: end - 30,
    end_timestamp_seconds: end,
    step_seconds: 5,
    series: Object.fromEntries(
      OVERVIEW_METRIC_GRAPHS.map((g) => [g.metric, [[end, 9]]])
    ),
    rolling_5m: Object.fromEntries(
      OVERVIEW_METRIC_GRAPHS.map((g) => [
        g.metric,
        {
          state: 'available',
          min: [[end, 1]],
          avg: [[end, 4]],
          max: [[end, 10]],
        },
      ])
    ),
  };
}
function group(
  status: StatusResponse | null = statusFixture(),
  nowMs = 109_000,
  statusError = false,
  error = false,
  history: OverviewHistoryBundle | null = bundle(),
  windowSeconds = 30
) {
  return (
    <OverviewMetricHistoryPanels
      status={status ?? undefined}
      statusError={statusError}
      history={history ?? undefined}
      error={error}
      selectedWindowSeconds={windowSeconds}
      nowMs={nowMs}
    />
  );
}
function latency(container: HTMLElement) {
  return container.querySelector(
    '[data-metric-panel="latency"]'
  )! as HTMLElement;
}
beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
    configurable: true,
    get: () => 400,
  });
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

describe('OverviewMetricHistoryPanels', () => {
  it('shares acquisition age and keeps normal provenance out of the visual layout', () => {
    const history = bundle(108);
    const view = render(group(statusFixture(), 109_000, false, false, history));
    expect(screen.getByText('Updated 4s ago')).toBeTruthy();
    expect(
      latency(view.container)
        .querySelector('.overview-metric-history__age')
        ?.classList.contains('overview-visually-hidden')
    ).toBe(true);
    expect(
      screen
        .getByLabelText('Graph traces')
        .classList.contains('overview-visually-hidden')
    ).toBe(true);
    view.rerender(
      group(
        { ...statusFixture(), timestamp: 'invalid' },
        109_000,
        false,
        false,
        history
      )
    );
    expect(screen.queryByText(/(?:Updated|Last observed) \d+s ago/)).toBeNull();
    expect(
      within(screen.getByLabelText('Network history context')).getByRole(
        'status'
      ).textContent
    ).toBe('Network unavailable');
  });

  it('formats both the current and retained stale value without touching plot values', () => {
    const history = bundle();
    const status = {
      ...statusFixture(),
      network: { ...statusFixture().network, latency_ms: 7.49 },
    };
    const view = render(group(status, 109_000, false, false, history));
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      '7 ms'
    );
    view.rerender(group(status, 130_000, false, false, history));
    expect(
      within(latency(view.container)).getByText('Last observed 7 ms · 25s old')
    ).toBeTruthy();
    expect(plot.setData).not.toHaveBeenCalled();
    expect(status.network.latency_ms).toBe(7.49);
  });

  // Catch using history values/evaluation times as current-value authority.
  it('shows five stationary status readouts with one truthful shared context', () => {
    const { container } = render(group());
    const panel = latency(container);
    expect(panel.querySelector('strong')?.textContent).toBe('7 ms');
    expect(
      within(panel).getByText(/^Observed 00:01:45 UTC; exact value/)
    ).toBeTruthy();
    expect(
      screen
        .getByLabelText('Downlink throughput history')
        .querySelector('strong')?.textContent
    ).toBe('0 Mbps');
    expect(
      screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    ).toEqual(['Latency', 'Downlink', 'Uplink', 'Packet loss', 'Obstruction']);
    expect(
      Array.from(
        container.querySelectorAll('.overview-metric-history__latest'),
        (node) => node.textContent
      )
    ).toEqual(['7 ms', '0 Mbps', '2 Mbps', '0.2%', '3%']);
    expect(subscriptions.status).not.toHaveBeenCalled();
    expect(subscriptions.history).not.toHaveBeenCalled();
    const header = screen.getByLabelText('Network history context');
    expect(within(header).getByRole('status').textContent).toBe(
      'Network fresh'
    );
    expect(within(header).getByText('LAST 30 SEC')).toBeTruthy();
    expect(within(header).getByText('fresh').className).toBe(
      'overview-visually-hidden'
    );
    expect(
      header.querySelector('.overview-metric-history-panels__error')
    ).toBeNull();
    expect(
      within(header).getByText('Rolling statistics: 5 minutes').className
    ).toBe('overview-visually-hidden');
    expect(within(header).queryByText('Rolling: 5 min')).toBeNull();
    expect(screen.getAllByLabelText('Graph traces')).toHaveLength(1);
    for (const text of ['Observed', 'Average (5m)', 'Low–high envelope (5m)'])
      expect(within(header).getByText(text)).toBeTruthy();
    expect(screen.queryByText('History available')).toBeNull();
    expect(screen.queryByText('Current network metrics')).toBeNull();
    expect(screen.queryByText(/signal quality/i)).toBeNull();
    const surface = panel.querySelector('.overview-metric-history__surface')!;
    expect(surface.contains(panel.querySelector('strong'))).toBe(false);
  });
  it.each([
    [300, 'LAST 5 MIN'],
    [900, 'LAST 15 MIN'],
    [1800, 'LAST 30 MIN'],
    [3600, 'LAST 60 MIN'],
    [1, 'LAST 1 SEC'],
    [75, 'LAST 75 SEC'],
  ])(
    'shows selected duration %s without changing the rolling window',
    (seconds, label) => {
      render(group(statusFixture(), 109_000, false, false, null, seconds));
      const header = screen.getByLabelText('Network history context');
      expect(within(header).getByText(label)).toBeTruthy();
      expect(
        within(header).getByText('Rolling statistics: 5 minutes')
      ).toBeTruthy();
    }
  );
  it('shows refresh exceptions only until their independent recovery', () => {
    const status = statusFixture();
    const history = bundle();
    const view = render(group(status, 109_000, true, true, history));
    const header = screen.getByLabelText('Network history context');
    expect(within(header).getByText('Status refresh unavailable')).toBeTruthy();
    expect(
      within(header).getByText('History refresh unavailable')
    ).toBeTruthy();
    expect(within(header).getByText('Last observed 4s ago')).toBeTruthy();
    view.rerender(group(status, 109_000, false, true, history));
    expect(within(header).queryByText('Status refresh unavailable')).toBeNull();
    expect(within(header).getByText('Updated 4s ago')).toBeTruthy();
    expect(
      within(header).getByText('History refresh unavailable')
    ).toBeTruthy();
    view.rerender(group(status, 109_000, false, false, history));
    expect(
      header.querySelector('.overview-metric-history-panels__error')
    ).toBeNull();
    expect(plot.setData).not.toHaveBeenCalled();
  });
  it('ages status independently of history without updating plot data', () => {
    const history = bundle();
    const status = statusFixture();
    const view = render(group(status, 109_000, false, false, history));
    view.rerender(group(status, 130_000, false, false, history));
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      'Unavailable'
    );
    expect(
      within(latency(view.container)).getByText('Last observed 7 ms · 25s old')
    ).toBeTruthy();
    expect(
      within(screen.getByLabelText('Network history context')).getByRole(
        'status'
      ).textContent
    ).toBe('Network stale');
    expect(plot.setData).not.toHaveBeenCalled();
  });
  it('keeps readouts stable as each status arrives between clock ticks', () => {
    const status = statusFixture();
    const history = bundle();
    const view = render(group(status, 105_000, false, false, history));
    for (let second = 105; second < 115; second += 1) {
      const timestamp = new Date(second * 1000 + 750).toISOString();
      for (const now of [second * 1000, (second + 1) * 1000]) {
        view.rerender(
          group({ ...status, timestamp }, now, false, false, history)
        );
        expect(
          latency(view.container).querySelector('strong')?.textContent
        ).toBe('7 ms');
        expect(
          within(screen.getByLabelText('Network history context')).getByRole(
            'status'
          ).textContent
        ).toBe('Network fresh');
      }
    }
    view.rerender(
      group(
        { ...status, timestamp: '1970-01-01T00:01:54.750Z' },
        124_750,
        false,
        false,
        history
      )
    );
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      'Unavailable'
    );
    expect(plot.setData).not.toHaveBeenCalled();
  });
  it('retains status on failed refresh but never presents it as current', () => {
    const view = render(group());
    view.rerender(group(null, 109_000, true));
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      'Unavailable'
    );
    expect(
      within(latency(view.container)).getByText('Last observed 7 ms · 4s old')
    ).toBeTruthy();
    expect(screen.getByText('Status refresh unavailable')).toBeTruthy();
  });
  it('separates history failure from a fresh status observation', () => {
    const view = render(group(statusFixture(), 109_000, false, true));
    expect(screen.getByText('History refresh unavailable')).toBeTruthy();
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      '7 ms'
    );
    expect(
      within(latency(view.container)).getByText(
        /^Observed 00:01:45 UTC; exact value/
      )
    ).toBeTruthy();
  });
  it.each(['legacy', 'null', 'false', 'future', 'invalid'] as const)(
    'fails closed for %s status',
    (kind) => {
      const status = statusFixture();
      if (kind === 'legacy') delete status.metric_availability;
      if (kind === 'null') status.network!.latency_ms = null;
      if (kind === 'false') {
        status.network!.latency_ms = 0;
        status.metric_availability!.latency_ms = false;
      }
      if (kind === 'future') status.timestamp = '1970-01-01T00:02:00Z';
      if (kind === 'invalid') status.timestamp = 'invalid';
      const view = render(group(status));
      expect(latency(view.container).querySelector('strong')?.textContent).toBe(
        'Unavailable'
      );
      expect(
        within(latency(view.container)).getByText('No timestamped observation')
      ).toBeTruthy();
    }
  );
  it('reports partial source availability without hiding verified zero', () => {
    const status = statusFixture();
    status.network!.latency_ms = null;
    render(group(status));
    expect(
      within(screen.getByLabelText('Network history context')).getByRole(
        'status'
      ).textContent
    ).toBe('Network partial');
    expect(
      screen
        .getByLabelText('Downlink throughput history')
        .querySelector('strong')?.textContent
    ).toBe('0 Mbps');
  });
  it.each([
    ['excessively future', '1970-01-01T00:02:00.000Z'],
    ['malformed', 'invalid'],
  ])(
    'recovers after %s timestamps without advancing accepted status',
    (_, timestamp) => {
      const status = statusFixture();
      const view = render(group(status));
      expect(latency(view.container).querySelector('strong')?.textContent).toBe(
        '7 ms'
      );

      view.rerender(
        group(
          {
            ...status,
            timestamp,
            network: { ...status.network, latency_ms: 99 },
          },
          109_000,
          false,
          false,
          bundle(110)
        )
      );
      expect(latency(view.container).querySelector('strong')?.textContent).toBe(
        'Unavailable'
      );
      expect(
        within(latency(view.container)).getByText('No timestamped observation')
      ).toBeTruthy();
      expect(
        within(screen.getByLabelText('Network history context')).getByRole(
          'status'
        ).textContent
      ).toBe('Network unavailable');
      expect(plot.setData.mock.calls[0][0][0]).toEqual([110]);

      // A failed poll must retain the valid sample, not the rejected one.
      view.rerender(group(null, 109_000, true, false, bundle(110)));
      expect(
        within(latency(view.container)).getByText('Last observed 7 ms · 4s old')
      ).toBeTruthy();

      const recovered = {
        ...status,
        timestamp: '1970-01-01T00:01:48.000Z',
        network: { ...status.network, latency_ms: 8 },
      };
      plot.setData.mockClear();
      view.rerender(group(recovered, 109_000, false, false, bundle(105)));
      expect(latency(view.container).querySelector('strong')?.textContent).toBe(
        '8 ms'
      );
      expect(
        within(screen.getByLabelText('Network history context')).getByRole(
          'status'
        ).textContent
      ).toBe('Network fresh');
      expect(screen.getByText('Updated 1s ago')).toBeTruthy();
      expect(screen.queryByText('Status refresh unavailable')).toBeNull();
      expect(plot.setData).not.toHaveBeenCalled();

      view.rerender(
        group(
          {
            ...status,
            timestamp: '1970-01-01T00:01:46.000Z',
            network: { ...status.network, latency_ms: 99 },
          },
          109_000,
          false,
          false,
          bundle(115)
        )
      );
      expect(latency(view.container).querySelector('strong')?.textContent).toBe(
        '8 ms'
      );
      expect(plot.setData.mock.calls[0][0][0]).toEqual([115]);
    }
  );
  it.each([
    ['1970-01-01T00:01:54.000Z', '8 ms', 'Network fresh'],
    ['1970-01-01T00:01:54.001Z', 'Unavailable', 'Network unavailable'],
  ])(
    'validates the five-second clock-skew boundary at %s',
    (timestamp, value, state) => {
      const status = statusFixture();
      const history = bundle();
      const view = render(group(status, 109_000, false, false, history));
      view.rerender(
        group(
          {
            ...status,
            timestamp,
            network: { ...status.network, latency_ms: 8 },
          },
          109_000,
          false,
          false,
          history
        )
      );
      expect(latency(view.container).querySelector('strong')?.textContent).toBe(
        value
      );
      expect(
        within(screen.getByLabelText('Network history context')).getByRole(
          'status'
        ).textContent
      ).toBe(state);
      expect(screen.queryByText('Updated 0s ago') !== null).toBe(
        state === 'Network fresh'
      );
      expect(plot.setData).not.toHaveBeenCalled();
    }
  );
  it('rejects older status and history independently and accepts their recoveries', () => {
    const history = bundle();
    const status = statusFixture();
    const view = render(group(status, 109_000, false, false, history));
    const older = {
      ...status,
      timestamp: '1970-01-01T00:01:40Z',
      network: { ...status.network, latency_ms: 99 },
    };
    view.rerender(group(older, 109_000, false, false, bundle(110)));
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      '7 ms'
    );
    expect(plot.setData.mock.calls[0][0][0]).toEqual([110]);
    const newer = {
      ...status,
      timestamp: '1970-01-01T00:01:48Z',
      network: { ...status.network, latency_ms: 8 },
    };
    plot.setData.mockClear();
    view.rerender(group(newer, 109_000, false, false, bundle(100)));
    expect(latency(view.container).querySelector('strong')?.textContent).toBe(
      '8 ms'
    );
    expect(plot.setData).not.toHaveBeenCalled();
    view.rerender(group(newer, 109_000, false, false, bundle(115)));
    expect(plot.setData.mock.calls[0][0][0]).toEqual([115]);
  });
  it('retains accepted history when refresh removes data and does not carry it across windows', () => {
    const view = render(group());
    view.rerender(group(statusFixture(), 109_000, false, true, null));
    expect(plot.create).toHaveBeenCalledTimes(5);
    expect(screen.getAllByRole('img')[0].getAttribute('aria-label')).toContain(
      'Last-known history'
    );
    view.rerender(group(statusFixture(), 109_000, false, true, bundle(), 60));
    expect(screen.getAllByRole('img')[0].getAttribute('aria-label')).toContain(
      'History unavailable'
    );
    expect(screen.getByText('LAST 1 MIN')).toBeTruthy();
  });
});
