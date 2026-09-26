/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';

vi.mock('../components/missions/MissionList', () => ({
  MissionList: ({ onCreateNew }: { onCreateNew: () => void }) => (
    <button onClick={onCreateNew}>Open create mission</button>
  ),
}));
vi.mock('../components/missions/ExportDialog', () => ({
  ExportDialog: () => null,
}));
vi.mock('../components/missions/ImportDialog', () => ({
  ImportDialog: () => null,
}));
vi.mock('../hooks/api/useMissions', () => ({
  useCreateMission: vi.fn(),
}));

import { useCreateMission } from '../hooks/api/useMissions';
import { MissionsPage } from './MissionsPage';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function CurrentLocation() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

function renderMissionsPage() {
  return render(
    <MemoryRouter initialEntries={['/missions']}>
      <MissionsPage />
      <CurrentLocation />
    </MemoryRouter>
  );
}

function openCreateDialog() {
  fireEvent.click(screen.getByRole('button', { name: 'Open create mission' }));
  fireEvent.change(screen.getByLabelText('Mission Name'), {
    target: { value: 'Acceptance Mission' },
  });
}

describe('MissionsPage create mission navigation', () => {
  it('navigates to the created mission detail after a successful create', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ id: 'created-mission' });
    vi.mocked(useCreateMission).mockReturnValue({
      isPending: false,
      mutateAsync,
    } as never);

    renderMissionsPage();
    openCreateDialog();
    fireEvent.click(screen.getByRole('button', { name: 'Create Mission' }));

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe(
        '/missions/created-mission'
      );
    });
  });

  it('does not navigate when creating a mission fails', async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error('create failed'));
    vi.mocked(useCreateMission).mockReturnValue({
      isPending: false,
      mutateAsync,
    } as never);

    renderMissionsPage();
    openCreateDialog();
    fireEvent.click(screen.getByRole('button', { name: 'Create Mission' }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1);
      expect(screen.getByRole('alert').textContent).toBe(
        'Unable to create mission: create failed'
      );
    });
    expect(screen.getByTestId('location').textContent).toBe('/missions');
    expect(screen.getByRole('dialog')).not.toBeNull();
  });
});
