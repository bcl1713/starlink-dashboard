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

async function request<T>(
  url: `/api/${string}`,
  config: AxiosRequestConfig | undefined,
  parse: (data: unknown, headers: unknown) => T
): Promise<T> {
  try {
    const response = await apiClient.get<unknown>(url, config);
    return parse(response.data, response.headers);
  } catch (error) {
    const cause = error instanceof Error ? error.cause : undefined;
    if (axios.isCancel(error)) throw error;
    if (axios.isCancel(cause)) throw cause;
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
  const config: AxiosRequestConfig =
    filter === '' ? { signal } : { params: { category: filter }, signal };
  return request('/api/pois/etas', config, (data) => parsePOIETAs(data));
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
