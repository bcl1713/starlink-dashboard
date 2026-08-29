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
