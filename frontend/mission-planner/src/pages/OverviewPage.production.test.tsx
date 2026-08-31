import { fireEvent, screen } from '@testing-library/react';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  finishOverviewProductionCycle,
  getOverviewProductionMocks,
  installOverviewProductionBrowser,
  renderWithOverviewClient,
  resolveOverviewProductionServices,
} from './OverviewPage/production-test-harness';
import { OverviewPage } from './OverviewPage';
import { OVERVIEW_PREFERENCES_STORAGE_KEY } from './OverviewPage/preferences';

const mocks = getOverviewProductionMocks();

describe('OverviewPage production composition', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-31T05:00:00.000Z'));
    installOverviewProductionBrowser();
    resolveOverviewProductionServices();
    mocks.createdPlots.length = 0;
    Object.values(mocks).forEach((value) => {
      if (typeof value === 'function' && 'mockClear' in value)
        value.mockClear();
    });
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem: vi.fn() },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('preserves real map, chart, live node, and controls through five scheduled cycles', async () => {
    const { container } = renderWithOverviewClient(<OverviewPage />);
    await finishOverviewProductionCycle();
    expect(
      screen.getByRole('heading', { name: 'Operations Overview' })
    ).toBeVisible();

    const map = screen.getByRole('region', { name: 'Operational map' });
    const live = container.querySelector('[aria-live="polite"]')?.firstChild;
    const latencyChart = screen.getByRole('img', {
      name: 'Network Latency chart',
    });
    const firstPlot = mocks.createdPlots[0];
    fireEvent.click(screen.getByRole('button', { name: 'Overview controls' }));
    fireEvent.change(screen.getByLabelText('POI category'), {
      target: { value: 'departure' },
    });
    fireEvent.click(screen.getByText('Operational layers'));
    const disclosure = container.querySelector('details');

    for (let count = 0; count < 5; count += 1) {
      await vi.advanceTimersByTimeAsync(1000);
      await finishOverviewProductionCycle();
      expect(screen.getByRole('region', { name: 'Operational map' })).toBe(map);
      expect(screen.getByRole('img', { name: 'Network Latency chart' })).toBe(
        latencyChart
      );
      expect(mocks.createdPlots[0]).toBe(firstPlot);
      expect(container.querySelector('[aria-live="polite"]')?.firstChild).toBe(
        live
      );
      expect(disclosure?.open).toBe(true);
      expect(screen.getByLabelText('POI category')).toHaveValue('departure');
    }
  });

  it('routes all production panel retry buttons to one manual refresh path', async () => {
    const failed = {
      code: 'request-failed',
      message: 'Source refresh failed.',
    };
    mocks.getStatus.mockRejectedValue(new Error('status'));
    mocks.getMonitoringHistory.mockRejectedValue(new Error('history'));
    mocks.getGroundEntryPoint.mockRejectedValue(new Error('gep'));
    mocks.getPOIETAs.mockRejectedValue(new Error('pois'));
    mocks.getSatelliteETAs.mockRejectedValue(new Error('satellites'));
    mocks.getMissionEventETAs.mockRejectedValue(new Error('mission-events'));
    mocks.getRouteCoordinates.mockRejectedValue(new Error('route'));
    mocks.getActiveXLink.mockRejectedValue(new Error('active-link'));
    renderWithOverviewClient(<OverviewPage />);
    await finishOverviewProductionCycle();

    const buttons = screen.getAllByRole('button', { name: 'Retry' });
    expect(buttons).toHaveLength(6);
    expect(screen.getAllByText(failed.message).length).toBeGreaterThanOrEqual(
      6
    );
    const before = mocks.getStatus.mock.calls.length;
    for (let index = 0; index < buttons.length; index += 1) {
      const button = screen.getAllByRole('button', { name: 'Retry' })[index];
      fireEvent.click(button);
      await finishOverviewProductionCycle();
    }
    expect(mocks.getStatus.mock.calls.length).toBe(before + 6);
  });

  it('persists each production preference action exactly once in StrictMode', async () => {
    const setItem = vi.fn();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem },
    });
    renderWithOverviewClient(
      <StrictMode>
        <OverviewPage />
      </StrictMode>
    );
    await finishOverviewProductionCycle();
    const map = screen.getByRole('region', { name: 'Operational map' });
    const chart = screen.getByRole('img', { name: 'Network Latency chart' });

    expect(
      writeState(setItem, () =>
        fireEvent.click(
          screen.getByRole('button', { name: 'Overview controls' })
        )
      ).disclosures.controlsExpanded
    ).toBe(true);
    expect(
      writeState(setItem, () =>
        fireEvent.change(screen.getByLabelText('Refresh cadence'), {
          target: { value: 'paused' },
        })
      ).refreshCadence
    ).toBe('paused');
    expect(
      writeState(setItem, () =>
        fireEvent.change(screen.getByLabelText('POI category'), {
          target: { value: 'departure' },
        })
      ).poiFilter
    ).toBe('departure');
    expect(
      writeState(setItem, () =>
        fireEvent.click(screen.getByRole('checkbox', { name: 'Weather Radar' }))
      ).radarEnabled
    ).toBe(false);
    expect(
      writeState(setItem, () =>
        fireEvent.click(screen.getByRole('button', { name: 'Clock settings' }))
      ).disclosures.clockSettingsExpanded
    ).toBe(true);

    fireEvent.change(screen.getByLabelText('Clock time zone'), {
      target: { value: 'Europe/London' },
    });
    fireEvent.change(screen.getByLabelText('Clock label'), {
      target: { value: 'London' },
    });
    expect(
      writeState(setItem, () =>
        fireEvent.click(screen.getByRole('button', { name: 'Add clock' }))
      ).clocks.at(-1)
    ).toMatchObject({ timeZone: 'Europe/London', label: 'London' });

    const tokyo = screen.getByLabelText('Relabel Tokyo');
    fireEvent.focus(tokyo);
    fireEvent.change(tokyo, { target: { value: 'Tokyo Ops' } });
    expect(
      writeState(setItem, () => fireEvent.blur(tokyo)).clocks.some(
        (clock: { label: string }) => clock.label === 'Tokyo Ops'
      )
    ).toBe(true);
    expect(
      writeState(setItem, () =>
        fireEvent.click(screen.getByRole('button', { name: 'Move Omaha up' }))
      ).clocks[2].label
    ).toBe('Omaha');
    expect(
      writeState(setItem, () =>
        fireEvent.click(screen.getByRole('button', { name: 'Remove London' }))
      ).clocks.some((clock: { label: string }) => clock.label === 'London')
    ).toBe(false);

    expect(screen.getByRole('region', { name: 'Operational map' })).toBe(map);
    expect(screen.getByRole('img', { name: 'Network Latency chart' })).toBe(
      chart
    );
  });
});

function writeState(setItem: ReturnType<typeof vi.fn>, action: () => void) {
  setItem.mockClear();
  action();
  expect(setItem).toHaveBeenCalledTimes(1);
  expect(setItem.mock.calls[0][0]).toBe(OVERVIEW_PREFERENCES_STORAGE_KEY);
  return JSON.parse(setItem.mock.calls[0][1] as string);
}
