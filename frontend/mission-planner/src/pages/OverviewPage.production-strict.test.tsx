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

describe('OverviewPage production StrictMode persistence', () => {
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
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('persists each production preference action exactly once in StrictMode', async () => {
    const setItem = vi.fn();
    installStorage(setItem);
    renderStrictOverview();
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
    addLondonClock();
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
  }, 20_000);

  it('composes rapid production preference actions from the latest StrictMode ref', async () => {
    const setItem = vi.fn();
    installStorage(setItem);
    renderStrictOverview();
    await finishOverviewProductionCycle();
    const map = screen.getByRole('region', { name: 'Operational map' });
    const chart = screen.getByRole('img', { name: 'Network Latency chart' });

    setItem.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Overview controls' }));
    fireEvent.change(screen.getByLabelText('Refresh cadence'), {
      target: { value: 'paused' },
    });
    fireEvent.change(screen.getByLabelText('POI category'), {
      target: { value: 'arrival' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Additional clocks' }));
    expect(setItem).toHaveBeenCalledTimes(4);
    expect(lastWrite(setItem)).toMatchObject({
      refreshCadence: 'paused',
      poiFilter: 'arrival',
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: true,
      },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Clock settings' }));
    addLondonClock();
    setItem.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Add clock' }));
    const tokyo = screen.getByLabelText('Relabel Tokyo');
    fireEvent.focus(tokyo);
    fireEvent.change(tokyo, { target: { value: 'Tokyo Ops' } });
    fireEvent.blur(tokyo);
    fireEvent.click(screen.getByRole('button', { name: 'Move Omaha up' }));
    expect(setItem).toHaveBeenCalledTimes(3);
    expect(
      lastWrite(setItem).clocks.map((clock: { label: string }) => clock.label)
    ).toEqual(['UTC (Zulu)', 'Washington DC', 'Omaha', 'Tokyo Ops', 'London']);
    expect(screen.getByRole('region', { name: 'Operational map' })).toBe(map);
    expect(screen.getByRole('img', { name: 'Network Latency chart' })).toBe(
      chart
    );
  }, 20_000);
});

function installStorage(setItem: ReturnType<typeof vi.fn>) {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: { getItem: vi.fn(() => null), setItem },
  });
}

function renderStrictOverview() {
  renderWithOverviewClient(
    <StrictMode>
      <OverviewPage />
    </StrictMode>
  );
}

function addLondonClock() {
  fireEvent.change(screen.getByLabelText('Clock time zone'), {
    target: { value: 'Europe/London' },
  });
  fireEvent.change(screen.getByLabelText('Clock label'), {
    target: { value: 'London' },
  });
}

function writeState(setItem: ReturnType<typeof vi.fn>, action: () => void) {
  setItem.mockClear();
  action();
  expect(setItem).toHaveBeenCalledTimes(1);
  expect(setItem.mock.calls[0][0]).toBe(OVERVIEW_PREFERENCES_STORAGE_KEY);
  return JSON.parse(setItem.mock.calls[0][1] as string);
}

function lastWrite(setItem: ReturnType<typeof vi.fn>) {
  return JSON.parse(setItem.mock.calls.at(-1)?.[1] as string);
}
