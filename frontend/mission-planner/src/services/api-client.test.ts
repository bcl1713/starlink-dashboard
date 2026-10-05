import { AxiosError } from 'axios';
import { expect, it } from 'vitest';
import { apiClient } from './api-client';
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
