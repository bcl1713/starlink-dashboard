import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

import {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
} from '../../services/monitoring-test-fixtures';
import { flushOverviewEffects } from './overview-test-harness';

const overviewProductionMocks = vi.hoisted(() => {
  const createdPlots: Array<{ root: HTMLElement }> = [];
  class MockUPlot {
    root = document.createElement('div');
    setData = vi.fn();
    setSize = vi.fn();
    destroy = vi.fn(() => this.root.remove());
    constructor(_options: unknown, _data: unknown, target?: HTMLElement) {
      this.root.className = 'uplot';
      this.root.setAttribute('data-testid', 'uplot-root');
      target?.append(this.root);
      createdPlots.push(this);
    }
  }
  return {
    createdPlots,
    MockUPlot,
    getStatus: vi.fn(),
    getMonitoringHistory: vi.fn(),
    getGroundEntryPoint: vi.fn(),
    getPOIETAs: vi.fn(),
    getSatelliteETAs: vi.fn(),
    getMissionEventETAs: vi.fn(),
    getRouteCoordinates: vi.fn(),
    getActiveXLink: vi.fn(),
    getRainViewerRadarTile: vi.fn(),
  };
});

vi.mock('uplot', () => ({ default: overviewProductionMocks.MockUPlot }));

vi.mock('../../services/monitoring', () => ({
  getStatus: overviewProductionMocks.getStatus,
  getMonitoringHistory: overviewProductionMocks.getMonitoringHistory,
  getGroundEntryPoint: overviewProductionMocks.getGroundEntryPoint,
  getPOIETAs: overviewProductionMocks.getPOIETAs,
  getSatelliteETAs: overviewProductionMocks.getSatelliteETAs,
  getMissionEventETAs: overviewProductionMocks.getMissionEventETAs,
  getRouteCoordinates: overviewProductionMocks.getRouteCoordinates,
  getActiveXLink: overviewProductionMocks.getActiveXLink,
  getRainViewerRadarTile: overviewProductionMocks.getRainViewerRadarTile,
}));

export function getOverviewProductionMocks() {
  return overviewProductionMocks;
}

export function clone<T>(value: T): T {
  return structuredClone(value);
}

export function resolveOverviewProductionServices() {
  overviewProductionMocks.getStatus.mockResolvedValue(clone(statusPayload));
  overviewProductionMocks.getMonitoringHistory.mockResolvedValue(
    clone(historyPayload)
  );
  overviewProductionMocks.getGroundEntryPoint.mockResolvedValue(
    clone(availableGep)
  );
  overviewProductionMocks.getPOIETAs.mockResolvedValue(clone(poiPayload));
  overviewProductionMocks.getSatelliteETAs.mockResolvedValue(clone(poiPayload));
  overviewProductionMocks.getMissionEventETAs.mockResolvedValue({
    pois: [],
    total: 0,
    timestamp: poiPayload.timestamp,
  });
  overviewProductionMocks.getRouteCoordinates.mockResolvedValue(
    clone(routePayload)
  );
  overviewProductionMocks.getActiveXLink.mockResolvedValue(
    clone(activeXLinkPayload)
  );
  overviewProductionMocks.getRainViewerRadarTile.mockResolvedValue({
    bytes: new Uint8Array([137, 80, 78, 71]).buffer,
    frameTimestamp: '1777294800',
  });
}

export function installOverviewProductionBrowser() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      media: query,
      matches: !query.includes('max-width'),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
  Object.defineProperty(window, 'ResizeObserver', {
    configurable: true,
    value: class ResizeObserver {
      observe() {}
      disconnect() {}
    },
  });
  Element.prototype.getBoundingClientRect = vi.fn(() => ({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 640,
    bottom: 240,
    width: 640,
    height: 240,
    toJSON: () => ({}),
  }));
  Object.defineProperty(HTMLImageElement.prototype, 'decode', {
    configurable: true,
    value: vi.fn(() => Promise.resolve()),
  });
}

export function renderWithOverviewClient(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>
  );
}

export async function finishOverviewProductionCycle() {
  await act(async () => {
    await flushOverviewEffects();
  });
}
