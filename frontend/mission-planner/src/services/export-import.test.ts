import { AxiosError, type AxiosResponse } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { exportImportApi, formatMissionImportError } from './export-import';
import { apiClient } from './api-client';

afterEach(() => vi.restoreAllMocks());

describe('mission download metadata', () => {
  it('requests compact lossless telemetry explicitly', async () => {
    const post = vi
      .spyOn(apiClient, 'post')
      .mockResolvedValue({ data: new Blob(['zip']), headers: {} });
    await exportImportApi.exportMissionDownload('m', {
      telemetryFormat: 'compact',
    });
    expect(post.mock.calls[0][2]).toMatchObject({
      params: { telemetry_format: 'compact' },
    });
  });
  it('waits for explicit ready state before fetching a cold package', async () => {
    const queued = { id: 'job', state: 'queued', stage: 'queued' };
    const ready = { ...queued, state: 'ready', stage: 'ready' };
    const blob = new Blob(['zip']);
    vi.spyOn(apiClient, 'post').mockResolvedValue({
      status: 202,
      data: new Blob([JSON.stringify(queued)]),
      headers: {},
    });
    const read = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValueOnce({ data: ready })
      .mockResolvedValueOnce({ data: blob, headers: {} });
    const progress = vi.fn();
    const result = await exportImportApi.exportMissionDownload('m', {
      onProgress: progress,
    });
    expect(result.blob).toBe(blob);
    expect(read.mock.calls.map((call) => call[0])).toEqual([
      '/api/v2/missions/m/export-preparations/job',
      '/api/v2/missions/m/export-preparations/job/download',
    ]);
    expect(progress.mock.calls.map((call) => call[0].stage)).toEqual([
      'queued',
      'ready',
    ]);
  });

  it('cancels the owned pending job on abort', async () => {
    const controller = new AbortController();
    vi.spyOn(apiClient, 'post').mockResolvedValue({
      status: 202,
      data: { id: 'job', state: 'queued', stage: 'queued' },
      headers: {},
    });
    vi.spyOn(apiClient, 'get').mockImplementation(async () => {
      controller.abort();
      throw new DOMException('Aborted', 'AbortError');
    });
    const cancel = vi
      .spyOn(apiClient, 'delete')
      .mockResolvedValue({ data: { state: 'cancelled' } });
    await expect(
      exportImportApi.exportMissionDownload('m', { signal: controller.signal })
    ).rejects.toThrow();
    expect(cancel).toHaveBeenCalledWith(
      '/api/v2/missions/m/export-preparations/job',
      expect.anything()
    );
  });

  it.each([
    [{}, undefined, undefined],
    [{ 'x-customer-briefing-status': 'included' }, 'included', undefined],
    [
      {
        'x-customer-briefing-status': 'omitted',
        'x-customer-briefing-warning': 'deadline',
      },
      'omitted',
      'deadline',
    ],
    [
      {
        'x-customer-briefing-status': 'omitted',
        'x-customer-briefing-warning': 'Private exception',
      },
      'omitted',
      'runtime',
    ],
    [{ 'x-customer-briefing-status': 'unexpected' }, undefined, undefined],
  ])(
    'preserves the blob and only safe headers: %o',
    async (headers, briefingStatus, warningCode) => {
      const blob = new Blob(['zip']);
      vi.spyOn(apiClient, 'post').mockResolvedValue({ data: blob, headers });
      expect(exportImportApi).toHaveProperty('exportMissionDownload');
      expect(await exportImportApi.exportMissionDownload('m')).toEqual({
        blob,
        briefingStatus,
        warningCode,
      });
    }
  );

  it('preserves the existing Blob wrapper', async () => {
    const blob = new Blob(['zip']);
    vi.spyOn(apiClient, 'post').mockResolvedValue({ data: blob, headers: {} });
    expect(await exportImportApi.exportMission('m')).toBe(blob);
  });
});

describe('formatMissionImportError', () => {
  it('identifies the proxy layer that rejected an oversized mission package', () => {
    const response = {
      data: {
        detail: {
          code: 'mission_package_too_large',
          layer: 'mission-planner-nginx',
          max_bytes: 100 * 1024 * 1024,
        },
      },
    } as AxiosResponse;
    const error = new AxiosError('Request failed with status code 413');
    error.response = response;

    expect(formatMissionImportError(error)).toBe(
      'Mission package exceeds the 100 MiB limit (rejected by mission-planner-nginx).'
    );
  });
});
