import { AxiosError, type AxiosResponse } from 'axios';
import { describe, expect, it } from 'vitest';

import { formatMissionDeletionError } from './mission-deletion';

describe('formatMissionDeletionError', () => {
  it('renders the active-leg deactivation action instead of a generic failure', () => {
    const error = new AxiosError('Request failed with status code 409');
    error.response = {
      data: {
        detail: {
          code: 'ACTIVE_LEG_DELETION_FORBIDDEN',
          action: 'Deactivate the leg, then delete it.',
        },
      },
    } as AxiosResponse;

    expect(formatMissionDeletionError(error)).toBe(
      'Deactivate the leg, then delete it.'
    );
  });
});
