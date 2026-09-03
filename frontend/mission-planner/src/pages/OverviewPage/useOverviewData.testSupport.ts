import { vi } from 'vitest';
import {
  fetchApplicablePois,
  fetchGroundEntryPoint,
  fetchHistory,
  fetchMapOverlays,
  fetchStatus,
  metricOrder,
} from '../../services/monitoring';

export const now = new Date('2026-09-02T12:00:00Z');
export const status = (latency = 20) => ({
  source: 'live' as const,
  timestamp: '2026-09-02T11:59:50Z',
  observed_at: '2026-09-02T11:59:50Z',
  received_at: '2026-09-02T11:59:51Z',
  position: { latitude: 41, longitude: -96, altitude: 1, speed: 0, heading: 0 },
  network: {
    latency_ms: latency,
    throughput_down_mbps: 100,
    throughput_up_mbps: 10,
    packet_loss_percent: 1,
  },
  obstruction: { obstruction_percent: 2 },
  environmental: {
    signal_quality_percent: 98,
    uptime_seconds: 10,
    temperature_celsius: null,
  },
});

export const history = () => ({
  generated_at: now.toISOString(),
  window_start: '2026-09-02T11:30:00Z',
  window_end: now.toISOString(),
  range_seconds: 1800,
  step_seconds: 1,
  series: metricOrder.map((metric) => ({
    metric,
    samples:
      metric === 'latency_ms'
        ? [{ timestamp: '2026-09-02T11:59:59Z', value: 999 }]
        : metric === 'packet_loss_percent'
          ? [
              { timestamp: '2026-09-02T11:54:59Z', value: 88 },
              { timestamp: '2026-09-02T11:59:59Z', value: 9 },
            ]
          : [],
  })),
});

export const poi = {
  poi_id: 'poi-1',
  name: 'Airport',
  category: null,
  eta_seconds: 60,
  distance_meters: 1000,
  active: true,
  latitude: 41,
  longitude: -96,
};
export const gep = {
  available: true,
  observed_at: now.toISOString(),
  generated_at: now.toISOString(),
  display: 'Omaha',
  city: 'Omaha',
  region: 'Nebraska',
  country: 'US',
  latitude: 41,
  longitude: -96,
};

export function setVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: state,
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

export function defaults() {
  vi.mocked(fetchStatus).mockResolvedValue(status());
  vi.mocked(fetchHistory).mockResolvedValue(history());
  vi.mocked(fetchGroundEntryPoint).mockResolvedValue(gep);
  vi.mocked(fetchApplicablePois).mockResolvedValue([poi]);
  vi.mocked(fetchMapOverlays).mockResolvedValue({
    route: { west: [], east: [] },
    activeLinks: {
      normal: { west: [], east: [] },
      warning: { west: [], east: [] },
    },
  });
}

export function resetOverviewMocks(): void {
  vi.useRealTimers();
  vi.clearAllMocks();
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: 'visible',
  });
}
