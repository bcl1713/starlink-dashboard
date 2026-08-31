import axios, { type AxiosRequestConfig } from 'axios';

import { apiClient } from './api-client';
import {
  parseActiveXLink,
  parseGroundEntryPoint,
  parseMonitoringHistory,
  parsePOIETAs,
  parseRainViewerRadarTile,
  parseRouteCoordinates,
  parseStatus,
  validateRadarXYZ,
} from './monitoring-schemas';
import type {
  ActiveXLink,
  GetMonitoringHistoryArgs,
  GetRainViewerRadarTileArgs,
  GroundEntryPoint,
  MonitoringHistory,
  OverviewStatus,
  POIETAFilter,
  POIETAResponse,
  RainViewerRadarTile,
  RouteCoordinates,
} from '../types/monitoring';

function safeIsCancel(value: unknown): boolean {
  try {
    return axios.isCancel(value);
  } catch {
    return false;
  }
}

function safeGetCause(value: unknown): unknown {
  if (
    (typeof value !== 'object' && typeof value !== 'function') ||
    value === null
  ) {
    return undefined;
  }
  try {
    return Reflect.get(value, 'cause');
  } catch {
    return undefined;
  }
}

async function request<T>(
  url: `/api/${string}`,
  config: AxiosRequestConfig | undefined,
  parse: (data: unknown, headers: unknown) => T
): Promise<T> {
  try {
    const response = await apiClient.get<unknown>(url, config);
    return parse(response.data, response.headers);
  } catch (error) {
    if (safeIsCancel(error)) throw error;
    const cause = safeGetCause(error);
    if (safeIsCancel(cause)) throw cause;
    throw error;
  }
}

export function getStatus(signal?: AbortSignal): Promise<OverviewStatus> {
  return request('/api/status', { signal }, (data) => parseStatus(data));
}

export function getMonitoringHistory({
  rangeSeconds = 1800,
  stepSeconds = 1,
  signal,
}: GetMonitoringHistoryArgs = {}): Promise<MonitoringHistory> {
  return request(
    '/api/monitoring/history',
    {
      params: {
        range_seconds: rangeSeconds,
        step_seconds: stepSeconds,
      },
      signal,
    },
    (data) => parseMonitoringHistory(data)
  );
}

export function getGroundEntryPoint(
  signal?: AbortSignal
): Promise<GroundEntryPoint> {
  return request('/api/monitoring/ground-entry-point', { signal }, (data) =>
    parseGroundEntryPoint(data)
  );
}

export function getPOIETAs(
  filter: POIETAFilter = 'departure,arrival',
  signal?: AbortSignal
): Promise<POIETAResponse> {
  const url =
    filter === ''
      ? '/api/pois/etas'
      : `/api/pois/etas?category=${encodeURIComponent(filter)}`;
  return request(url as `/api/${string}`, { signal }, (data) =>
    parsePOIETAs(data)
  );
}

export function getSatelliteETAs(
  signal?: AbortSignal
): Promise<POIETAResponse> {
  return getPOIETAs('satellite', signal);
}

export function getMissionEventETAs(
  signal?: AbortSignal
): Promise<POIETAResponse> {
  return getPOIETAs('mission-event', signal);
}

export function getRouteCoordinates(
  direction: 'west' | 'east',
  signal?: AbortSignal
): Promise<RouteCoordinates> {
  return request(`/api/route/coordinates/${direction}`, { signal }, (data) =>
    parseRouteCoordinates(data)
  );
}

export function getActiveXLink(
  state: 'normal' | 'warning',
  signal?: AbortSignal
): Promise<ActiveXLink> {
  return request('/api/active-x-link', { params: { state }, signal }, (data) =>
    parseActiveXLink(data)
  );
}

export async function getRainViewerRadarTile({
  z,
  x,
  y,
  signal,
}: GetRainViewerRadarTileArgs): Promise<RainViewerRadarTile> {
  validateRadarXYZ(z, x, y);
  return request(
    `/api/weather/radar/rainviewer/${z}/${x}/${y}.png`,
    { responseType: 'arraybuffer', signal },
    parseRainViewerRadarTile
  );
}
