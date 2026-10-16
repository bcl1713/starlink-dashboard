import { apiClient } from './api-client';
import type { ImportOperation } from '../types/itinerary-import';
const base = '/api/v2/missions/itinerary-imports';
export const itineraryImportApi = {
  async start(
    pdf: File | null,
    kmls: File[],
    key: string,
    missionId?: string
  ): Promise<ImportOperation> {
    if (
      (pdf?.size ?? 0) > 10 * 1024 * 1024 ||
      kmls.length > 16 ||
      kmls.reduce((s, f) => s + f.size, 0) > 40 * 1024 * 1024
    )
      throw new Error(
        'Use a PDF up to 10 MiB and up to 16 KMLs, totaling 40 MiB.'
      );
    const body = new FormData();
    if (pdf) body.append('pdf', pdf);
    for (const file of kmls) body.append('kmls', file);
    body.append('idempotency_key', key);
    if (missionId) body.append('mission_id', missionId);
    return (
      await apiClient.post(base, body, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000,
      })
    ).data;
  },
  async read(id: string, signal?: AbortSignal): Promise<ImportOperation> {
    return (
      await apiClient.get(`${base}/${encodeURIComponent(id)}`, { signal })
    ).data;
  },
  async cancel(id: string): Promise<ImportOperation> {
    return (await apiClient.delete(`${base}/${encodeURIComponent(id)}`)).data;
  },
  async resolve(
    id: string,
    generation: number,
    choices: Record<string, unknown>
  ): Promise<ImportOperation> {
    return (
      await apiClient.post(`${base}/${encodeURIComponent(id)}/resolutions`, {
        generation,
        choices,
      })
    ).data;
  },
  async commit(
    id: string,
    generation: number,
    choices: Record<string, string>
  ): Promise<ImportOperation> {
    return (
      await apiClient.post(
        `${base}/${encodeURIComponent(id)}/commit`,
        { generation, choices },
        { timeout: 180000 }
      )
    ).data;
  },
};
