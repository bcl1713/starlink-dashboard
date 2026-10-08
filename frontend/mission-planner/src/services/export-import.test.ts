import { AxiosError, type AxiosResponse } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { exportImportApi, formatMissionImportError } from './export-import';
import { apiClient } from './api-client';

afterEach(() => vi.restoreAllMocks());

describe('mission download metadata', () => {
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
