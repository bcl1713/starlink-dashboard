import { AxiosError, type AxiosResponse } from 'axios';
import { describe, expect, it } from 'vitest';

import { formatMissionImportError } from './export-import';

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

import { afterEach, vi } from 'vitest';
import { apiClient } from './api-client';
import { exportImportApi } from './export-import';

afterEach(() => vi.restoreAllMocks());

describe('mission export result', () => {
  it('returns the downloaded blob and trial warnings while preserving the Blob API', async () => {
    const blob = new Blob(['legacy zip']);
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: blob,
      headers: {
        'x-mission-export-trial-status': 'failed',
        'x-mission-export-warnings': JSON.stringify([
          'Customer briefing — Trial could not be generated. Legacy exports are included.',
        ]),
      },
    });
    const result = await exportImportApi.exportMissionResult('m');
    expect(result.blob).toBe(blob);
    expect(result.warnings).toEqual([
      'Customer briefing — Trial could not be generated. Legacy exports are included.',
    ]);
    expect(await exportImportApi.exportMission('m')).toBe(blob);
    expect(post).toHaveBeenCalledWith(
      '/api/v2/missions/m/export',
      {},
      { responseType: 'blob' }
    );
  });

  it.each([undefined, '', 'broken json', '{}', '[1, null]', '[]'])(
    'downloads normally with missing or malformed warnings %s',
    async (header) => {
      const blob = new Blob(['zip']);
      vi.spyOn(apiClient, 'post').mockResolvedValue({
        data: blob,
        headers: { 'x-mission-export-warnings': header },
      });
      expect(await exportImportApi.exportMissionResult('m')).toEqual({
        blob,
        warnings: [],
      });
    }
  );

  it('keeps a failed-trial warning visible if its warning header is absent', async () => {
    const blob = new Blob(['zip']);
    vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: blob,
      headers: { 'x-mission-export-trial-status': 'failed' },
    });
    const result = await exportImportApi.exportMissionResult('m');
    expect(result.blob).toBe(blob);
    expect(result.warnings.join(' ')).toMatch(/Trial.*could not/i);
  });

  it('bounds warning input and rejects control characters', async () => {
    const blob = new Blob(['zip']);
    vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: blob,
      headers: {
        'x-mission-export-warnings': JSON.stringify([
          'ok\r\nforged',
          'x'.repeat(3000),
        ]),
      },
    });
    expect((await exportImportApi.exportMissionResult('m')).warnings).toEqual(
      []
    );
  });

  it('propagates a failed ZIP request', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(new Error('Network failure'));
    await expect(exportImportApi.exportMissionResult('m')).rejects.toThrow(
      'Network failure'
    );
  });
});
