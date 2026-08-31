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

const LAYOUT_QUERIES = [
  '(min-width: 1536px)',
  '(min-width: 1024px) and (max-width: 1535px)',
  '(min-width: 768px) and (max-width: 1023px)',
  '(max-width: 767px)',
] as const;

type LayoutQuery = (typeof LAYOUT_QUERIES)[number];
type LayoutListener = (event: MediaQueryListEvent) => void;

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

export function overviewLayoutCounts(expected: {
  readonly add: number;
  readonly remove: number;
  readonly active: number;
}) {
  return Object.fromEntries(
    LAYOUT_QUERIES.map((query) => [query, { ...expected }])
  );
}

export function installTrackedOverviewLayoutMedia(width: number) {
  const records = new Map<
    LayoutQuery,
    {
      listeners: Set<LayoutListener>;
      list: MediaQueryList;
      add: number;
      remove: number;
    }
  >();

  const matches = (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)?.[1];
    const max = /max-width:\s*(\d+)px/.exec(query)?.[1];
    return (!min || width >= Number(min)) && (!max || width <= Number(max));
  };

  const matchMedia = (query: string) => {
    if (!isOverviewLayoutQuery(query)) {
      return {
        media: query,
        matches: matches(query),
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      } as unknown as MediaQueryList;
    }
    const layoutQuery = query as LayoutQuery;
    const record = records.get(layoutQuery) ?? {
      listeners: new Set<LayoutListener>(),
      add: 0,
      remove: 0,
      list: {
        media: query,
        matches: matches(query),
        onchange: null,
        addEventListener: (_type: string, listener: LayoutListener) => {
          record.add += 1;
          record.listeners.add(listener);
        },
        removeEventListener: (_type: string, listener: LayoutListener) => {
          record.remove += 1;
          record.listeners.delete(listener);
        },
        addListener: (listener: LayoutListener) =>
          record.listeners.add(listener),
        removeListener: (listener: LayoutListener) =>
          record.listeners.delete(listener),
        dispatchEvent: () => true,
      } as MediaQueryList,
    };
    Object.defineProperty(record.list, 'matches', {
      configurable: true,
      value: matches(query),
    });
    records.set(layoutQuery, record);
    return record.list;
  };
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: matchMedia,
  });

  return {
    resize(nextWidth: number) {
      width = nextWidth;
      for (const [query, record] of records) {
        const next = matches(query);
        Object.defineProperty(record.list, 'matches', {
          configurable: true,
          value: next,
        });
        const event = { matches: next, media: query };
        for (const listener of record.listeners) {
          listener(event as MediaQueryListEvent);
        }
      }
    },
    countsByQuery() {
      return Object.fromEntries(
        LAYOUT_QUERIES.map((query) => {
          const record = records.get(query);
          return [
            query,
            {
              add: record?.add ?? 0,
              remove: record?.remove ?? 0,
              active: record?.listeners.size ?? 0,
            },
          ];
        })
      );
    },
    liveListenerCount() {
      return Array.from(records.values()).reduce(
        (total, record) => total + record.listeners.size,
        0
      );
    },
  };
}

function isOverviewLayoutQuery(query: string): query is LayoutQuery {
  return LAYOUT_QUERIES.includes(query as LayoutQuery);
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
