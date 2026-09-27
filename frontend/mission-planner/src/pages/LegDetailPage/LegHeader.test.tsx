/** @vitest-environment jsdom */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LegHeader } from './LegHeader';

const mutateAsync = vi.fn();
vi.mock('../../hooks/api/useMissions', () => ({
  useUpdateLegRoute: () => ({ mutateAsync, isPending: false }),
}));

describe('LegHeader route replacement feedback', () => {
  it('shows the server lifecycle instruction for the active-route replacement conflict', async () => {
    mutateAsync.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            code: 'ACTIVE_LEG_ROUTE_REPLACEMENT_FORBIDDEN',
            action:
              'Deactivate the leg, upload the replacement route, then activate the leg again.',
          },
        },
      },
    });
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => undefined);
    render(
      <LegHeader missionId="mission-1" legId="leg-1" onBackClick={vi.fn()} />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Update Route' }));
    fireEvent.change(document.querySelector('input[type="file"]')!, {
      target: {
        files: [
          new File(['kml'], 'replacement.kml', {
            type: 'application/vnd.google-earth.kml+xml',
          }),
        ],
      },
    });

    await waitFor(() =>
      expect(alert).toHaveBeenCalledWith(
        'Deactivate the leg, upload the replacement route, then activate the leg again.'
      )
    );
    expect(alert).not.toHaveBeenCalledWith('Route updated successfully!');
    consoleError.mockRestore();
    alert.mockRestore();
  });
});
