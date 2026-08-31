import { fireEvent, screen } from '@testing-library/react';
import L from 'leaflet';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  finishOverviewProductionCycle,
  getOverviewProductionMocks,
  installOverviewProductionBrowser,
  renderWithOverviewClient,
  resolveOverviewProductionServices,
} from './OverviewPage/production-test-harness';
import { OverviewPage } from './OverviewPage';

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

  it('preserves real map, chart, live node, and controls through five scheduled cycles plus manual refresh', async () => {
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
    fireEvent.click(screen.getAllByRole('button', { name: 'Departure' })[0]);
    const disclosure = container.querySelector('details');
    const beforeManual = mocks.getStatus.mock.calls.length;

    for (let count = 0; count < 5; count += 1) {
      await vi.advanceTimersByTimeAsync(1000);
      await finishOverviewProductionCycle();
      assertProductionIdentity(container, map, latencyChart, firstPlot, live);
      expectProductionState(disclosure);
    }

    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));
    await finishOverviewProductionCycle();
    expect(mocks.getStatus.mock.calls.length).toBeGreaterThan(beforeManual);
    assertProductionIdentity(container, map, latencyChart, firstPlot, live);
    expectProductionState(disclosure);
    expect(
      screen.getByRole('region', { name: 'Feature details' })
    ).toHaveTextContent('Departure');
  }, 20_000);

  it('focuses the production ground entry point through the Leaflet map boundary', async () => {
    const reduced = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          media: query,
          matches: query.includes('prefers-reduced-motion'),
          onchange: null,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          addListener: vi.fn(),
          removeListener: vi.fn(),
          dispatchEvent: vi.fn(),
        }) as MediaQueryList
    );
    const setView = vi.spyOn(L.Map.prototype, 'setView');
    renderWithOverviewClient(<OverviewPage />);
    await finishOverviewProductionCycle();

    fireEvent.click(screen.getByRole('button', { name: 'Focus map' }));
    const focusCall = setView.mock.calls.find(
      ([center, zoom]) =>
        Array.isArray(center) &&
        center[0] === 39.7392 &&
        center[1] === -104.9903 &&
        zoom === 8
    );
    expect(focusCall?.[2]).toMatchObject({ animate: false });

    setView.mockRestore();
    reduced.mockRestore();
  });

  it('preserves production state and owners through inline native kiosk inline fullscreen modes', async () => {
    const { container } = renderWithOverviewClient(<OverviewPage />);
    await finishOverviewProductionCycle();
    const page = container.querySelector('.overview-page') as HTMLElement;
    const map = screen.getByRole('region', { name: 'Operational map' });
    const chart = screen.getByRole('img', { name: 'Network Latency chart' });
    const firstPlot = mocks.createdPlots[0];
    const live = container.querySelector('[aria-live="polite"]')?.firstChild;
    const request = vi.fn(() => new Promise<void>(() => {}));
    page.requestFullscreen = request;
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: page,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Overview controls' }));
    fireEvent.change(screen.getByLabelText('POI category'), {
      target: { value: 'arrival' },
    });
    fireEvent.click(screen.getByText('Operational layers'));
    fireEvent.click(screen.getAllByRole('button', { name: 'Departure' })[0]);
    const disclosure = container.querySelector('details');

    fireEvent.click(screen.getByRole('button', { name: 'Enter fullscreen' }));
    expect(
      screen.getByRole('button', { name: 'Enter fullscreen' })
    ).toBeDisabled();
    fireEvent(document, new Event('fullscreenchange'));
    expect(page).toHaveClass('overview-page--native');
    assertProductionIdentity(container, map, chart, firstPlot, live);
    expectProductionState(disclosure, 'arrival');

    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: null,
    });
    fireEvent(document, new Event('fullscreenchange'));
    page.requestFullscreen = vi.fn(() => Promise.reject(new Error('blocked')));
    fireEvent.click(screen.getByRole('button', { name: 'Enter fullscreen' }));
    await finishOverviewProductionCycle();
    expect(
      screen.getByRole('button', { name: 'Exit kiosk view' })
    ).toBeVisible();
    assertProductionIdentity(container, map, chart, firstPlot, live);
    expectProductionState(disclosure, 'arrival');

    fireEvent.click(screen.getByRole('button', { name: 'Exit kiosk view' }));
    expect(page).toHaveClass('overview-page--inline');
    assertProductionIdentity(container, map, chart, firstPlot, live);
    expectProductionState(disclosure, 'arrival');
    expect(request).toHaveBeenCalledTimes(1);
  }, 20_000);

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
});

function assertProductionIdentity(
  container: HTMLElement,
  map: HTMLElement,
  chart: HTMLElement,
  plot: { root: HTMLElement },
  live: ChildNode | null | undefined
) {
  expect(screen.getByRole('region', { name: 'Operational map' })).toBe(map);
  expect(screen.getByRole('img', { name: 'Network Latency chart' })).toBe(
    chart
  );
  expect(mocks.createdPlots[0]).toBe(plot);
  expect(container.querySelector('[aria-live="polite"]')?.firstChild).toBe(
    live
  );
}

function expectProductionState(
  disclosure: HTMLDetailsElement | null,
  poi = 'departure'
) {
  expect(disclosure?.open).toBe(true);
  expect(screen.getByLabelText('POI category')).toHaveValue(poi);
  expect(
    screen.getByRole('button', { name: 'Overview controls' })
  ).toHaveAttribute('aria-expanded', 'true');
}
