import type { DetailContext, DetailPair } from './weather-detail';
import type { DetailDemand } from './weather-detail-selection';
import type { WeatherWork } from './weather-work';
import type { WeatherAtlasPair } from './weather-atlas';

export type BrowserWeatherClock = { nowMono(): number };
export const browserWeatherClock: BrowserWeatherClock = {
  nowMono: () => performance.now(),
};
export type WeatherLayerView = {
  detailContext: DetailContext | null;
  detailPairs: readonly DetailPair[];
  work: WeatherWork | null;
  onDemand: (demand: DetailDemand) => void;
  configuredEnabled: boolean;
  visible: boolean;
  state: 'off' | 'loading' | 'current' | 'stale' | 'unavailable';
  frameTimeMs: number | null;
  ageMs: number | null;
  atlas: WeatherAtlasPair | null;
};
export const emptyWeatherView: WeatherLayerView = {
  detailContext: null,
  detailPairs: [],
  work: null,
  onDemand: () => {},
  configuredEnabled: false,
  visible: false,
  state: 'off',
  frameTimeMs: null,
  ageMs: null,
  atlas: null,
};
export function frameState(
  frameTimeMs: number,
  nowUtcMs: number,
  failed: boolean
) {
  const age = Math.max(0, nowUtcMs - frameTimeMs);
  if (age >= 3600000) return 'unavailable';
  return failed || age > 1200000 ? 'stale' : 'current';
}

/** Abort promises promptly; native work must still release eventual resources. */
export function abortable<T>(
  promise: Promise<T>,
  signal: AbortSignal
): Promise<T> {
  return new Promise((resolve, reject) => {
    const abort = () =>
      reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
    if (signal.aborted) {
      abort();
    } else {
      signal.addEventListener('abort', abort, { once: true });
    }
    promise
      .then(resolve, reject)
      .finally(() => signal.removeEventListener('abort', abort));
  });
}
