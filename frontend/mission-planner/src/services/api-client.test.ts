import { AxiosError, CanceledError } from 'axios';
import { expect, it, vi } from 'vitest';
import { apiClient } from './api-client';
it('decodes a safe capacity error when a ZIP request receives JSON as a Blob', async () => {
  await expect(
    apiClient.get('/export', {
      responseType: 'blob',
      adapter: async (config) => {
        throw new AxiosError(
          'Request failed',
          'ERR_BAD_REQUEST',
          config,
          undefined,
          {
            status: 413,
            statusText: 'Too large',
            data: new Blob(
              [
                JSON.stringify({
                  detail: {
                    code: 'mission_archive_capacity',
                    message:
                      'Mission export exceeds the supplementary-members capacity.',
                  },
                }),
              ],
              { type: 'application/json' }
            ),
            headers: {},
            config,
          }
        );
      },
    })
  ).rejects.toThrow(
    'Mission export exceeds the supplementary-members capacity.'
  );
});
it('retains intentional cancellation without reporting an API failure', async () => {
  const error = new CanceledError('obsolete preview');
  const log = vi.spyOn(console, 'error').mockImplementation(() => {});
  try {
    await expect(
      apiClient.get('/preview', {
        adapter: async () => {
          throw error;
        },
      })
    ).rejects.toBe(error);
    expect(log).not.toHaveBeenCalled();
  } finally {
    log.mockRestore();
  }
});
it.each([
  [
    [
      {
        loc: ['body', 'pacing'],
        msg: 'Effective multiplier must be between 0.1 and 1000',
        type: 'value_error',
      },
    ],
    'Effective multiplier must be between 0.1 and 1000',
  ],
  [
    { message: 'Simulation plan changed; preview again', simulation_run: {} },
    'Simulation plan changed; preview again',
  ],
  ['Legacy explanation', 'Legacy explanation'],
])('renders backend detail as actionable text', async (detail, message) => {
  await expect(
    apiClient.get('/api/simulation/run', {
      adapter: async (config) => {
        throw new AxiosError(
          'Request failed',
          'ERR_BAD_REQUEST',
          config,
          undefined,
          {
            status: Array.isArray(detail) ? 422 : 409,
            statusText: 'Rejected',
            data: { detail },
            headers: {},
            config,
          }
        );
      },
    })
  ).rejects.toThrow(message);
});
