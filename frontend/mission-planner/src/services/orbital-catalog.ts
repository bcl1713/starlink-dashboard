import apiClient from './api-client';
import {
  ELEMENT_FIELDS,
  MAX_OBJECTS,
  type CatalogEnvelope,
  type OrbitalDiagnostics,
} from '@/pages/orbital/types';

function confirmedCatalog(data: unknown): CatalogEnvelope {
  const d = data as CatalogEnvelope | null;
  if (
    !d ||
    !Array.isArray(d.objects) ||
    d.objects.length > MAX_OBJECTS ||
    typeof d.generation !== 'string' ||
    typeof d.suspended !== 'boolean' ||
    typeof d.status !== 'string' ||
    ![d.rejected_count, d.truncated_count, d.eligible_count].every(
      (v) => Number.isInteger(v) && v >= 0
    ) ||
    ![d.acquired_at, d.last_attempt_at, d.retry_after_at].every(
      (v) =>
        v === null || (typeof v === 'string' && Number.isFinite(Date.parse(v)))
    ) ||
    d.objects.some(
      (obj) =>
        !obj ||
        typeof obj.NORAD_CAT_ID !== 'string' ||
        !/^[1-9]\d{0,8}$/.test(obj.NORAD_CAT_ID) ||
        !Number.isFinite(Date.parse(obj.EPOCH)) ||
        !ELEMENT_FIELDS.every(
          (key) => typeof obj[key] === 'number' && Number.isFinite(obj[key])
        )
    ) ||
    new Set(d.objects.map((obj) => obj.NORAD_CAT_ID)).size !== d.objects.length
  )
    throw new Error('Invalid orbital catalog');
  return d;
}
export const orbitalCatalogApi = {
  async acquire(
    viewerId: string,
    signal?: AbortSignal
  ): Promise<{ expires_at: string }> {
    const { data } = await apiClient.put(
      `/api/orbital/viewers/${encodeURIComponent(viewerId)}`,
      undefined,
      { signal }
    );
    if (
      !data ||
      typeof data.expires_at !== 'string' ||
      !Number.isFinite(Date.parse(data.expires_at))
    )
      throw new Error('Invalid orbital lease');
    return data;
  },
  async release(viewerId: string): Promise<void> {
    await apiClient.delete(
      `/api/orbital/viewers/${encodeURIComponent(viewerId)}`
    );
  },
  async catalog(
    viewerId: string,
    signal?: AbortSignal
  ): Promise<CatalogEnvelope> {
    const { data } = await apiClient.get('/api/orbital/catalog', {
      params: { viewer_id: viewerId },
      signal,
    });
    return confirmedCatalog(data);
  },
  async status(signal?: AbortSignal): Promise<OrbitalDiagnostics> {
    const { data } = await apiClient.get('/api/orbital/status', { signal });
    return data;
  },
  async resume(): Promise<OrbitalDiagnostics> {
    const { data } = await apiClient.post('/api/orbital/provider/resume');
    return data;
  },
};
