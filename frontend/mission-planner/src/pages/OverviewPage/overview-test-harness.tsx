import { vi } from 'vitest';

import {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
  unavailableGep,
} from '../../services/monitoring-test-fixtures';
import type {
  ActiveXLink,
  GroundEntryPoint,
  MonitoringHistory,
  OverviewStatus,
  POIETAResponse,
  RouteCoordinates,
} from '../../types/monitoring';
import type { OverviewDataServices } from './overview-data-types';

export {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
  unavailableGep,
};

export const OVERVIEW_TEST_NOW = 1_777_294_800_000;

export async function flushOverviewEffects(): Promise<void> {
  for (let count = 0; count < 8; count += 1) {
    await Promise.resolve();
  }
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

export function cloneFixture<T>(value: T): T {
  return structuredClone(value);
}

export function createOverviewServices(
  overrides: Partial<OverviewDataServices> = {}
): OverviewDataServices {
  return {
    getStatus: vi.fn(() => Promise.resolve(cloneFixture(statusPayload))),
    getMonitoringHistory: vi.fn(() =>
      Promise.resolve(cloneFixture(historyPayload))
    ),
    getGroundEntryPoint: vi.fn(() =>
      Promise.resolve(cloneFixture(availableGep))
    ),
    getPOIETAs: vi.fn(() => Promise.resolve(cloneFixture(poiPayload))),
    getSatelliteETAs: vi.fn(() => Promise.resolve(cloneFixture(poiPayload))),
    getMissionEventETAs: vi.fn(() => Promise.resolve(cloneFixture(poiPayload))),
    getRouteCoordinates: vi.fn(() =>
      Promise.resolve(cloneFixture(routePayload))
    ),
    getActiveXLink: vi.fn(() =>
      Promise.resolve(cloneFixture(activeXLinkPayload))
    ),
    ...overrides,
  } as unknown as OverviewDataServices;
}

export function createCallCountingServices(
  overrides: Partial<OverviewDataServices> = {}
) {
  const calls: string[] = [];
  const record = <T,>(name: string, value: T) =>
    vi.fn(() => {
      calls.push(name);
      return Promise.resolve(cloneFixture(value));
    });
  const svc = {
    getStatus: record('status', statusPayload),
    getMonitoringHistory: record('history', historyPayload),
    getGroundEntryPoint: record('gep', availableGep),
    getPOIETAs: record('pois', poiPayload),
    getSatelliteETAs: record('satellites', poiPayload),
    getMissionEventETAs: record('missionEvents', poiPayload),
    getRouteCoordinates: vi.fn((direction: 'west' | 'east') => {
      calls.push(direction);
      return Promise.resolve(cloneFixture(routePayload));
    }),
    getActiveXLink: vi.fn((state: 'normal' | 'warning') => {
      calls.push(state);
      return Promise.resolve({
        ...cloneFixture(activeXLinkPayload),
        state,
      } as ActiveXLink);
    }),
    ...overrides,
  } as unknown as OverviewDataServices;
  return { calls, svc };
}

export function createDeferredSlotServices() {
  const signals: AbortSignal[] = [];
  const gates: ReturnType<typeof deferred<unknown>>[] = [];
  const never = <T,>(signal: AbortSignal | undefined): Promise<T> => {
    const gate = deferred<unknown>();
    if (signal) {
      signals.push(signal);
    }
    gates.push(gate);
    return gate.promise as Promise<T>;
  };
  const svc = createOverviewServices();
  svc.getStatus = vi.fn((signal) => never<OverviewStatus>(signal));
  svc.getPOIETAs = vi.fn((_filter, signal) => never<POIETAResponse>(signal));
  svc.getSatelliteETAs = vi.fn((signal) => never<POIETAResponse>(signal));
  svc.getMissionEventETAs = vi.fn((signal) => never<POIETAResponse>(signal));
  svc.getActiveXLink = vi.fn((_state, signal) => never<ActiveXLink>(signal));
  svc.getRouteCoordinates = vi.fn((_direction, signal) =>
    never<RouteCoordinates>(signal)
  );
  svc.getGroundEntryPoint = vi.fn((signal) => never<GroundEntryPoint>(signal));
  svc.getMonitoringHistory = vi.fn((args) =>
    never<MonitoringHistory>(args.signal)
  );
  return { gates, signals, svc };
}

export function captureReactWarnings() {
  const observed: string[] = [];
  const capture = (...args: unknown[]) => {
    const text = args.map(String).join('\n');
    if (/act\(|flushSync|unmounted component/i.test(text)) {
      observed.push(text);
    }
  };
  const errorSpy = vi.spyOn(console, 'error').mockImplementation(capture);
  const warnSpy = vi.spyOn(console, 'warn').mockImplementation(capture);
  return {
    observed,
    restore() {
      errorSpy.mockRestore();
      warnSpy.mockRestore();
    },
  };
}

export type {
  ActiveXLink,
  GroundEntryPoint,
  MonitoringHistory,
  OverviewStatus,
  POIETAResponse,
  RouteCoordinates,
};
