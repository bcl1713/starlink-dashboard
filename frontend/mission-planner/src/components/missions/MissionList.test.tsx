/** @vitest-environment jsdom */
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { MissionList } from './MissionList';
import { missionsApi, MISSIONS_PAGE_SIZE } from '../../services/missions';
import { rememberMission } from '../../services/mission-cache';
import type { Mission } from '../../types/mission';
const mission = (count: number, updated: string) =>
  ({
    id: 'm',
    name: 'Published mission',
    created_at: '2026-10-14T00:00:00Z',
    updated_at: updated,
    metadata: {},
    legs: Array.from({ length: count }, (_, index) => ({ id: 'leg-' + index })),
  }) as Mission;
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it('metadata-only list does not flash zero after publication or an older pending read', async () => {
  const client = new QueryClient();
  const original = mission(0, '2026-10-14T00:00:00Z');
  client.setQueryData(['missions', { limit: MISSIONS_PAGE_SIZE, offset: 0 }], {
    missions: [original],
    total: 1,
  });
  let release!: (value: { missions: Mission[]; total: number }) => void;
  vi.spyOn(missionsApi, 'listPage').mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve;
      })
  );
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MissionList
          onCreateNew={() => {}}
          onImport={() => {}}
          onExport={() => {}}
          onSelectMission={() => {}}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  await waitFor(() => expect(release).toBeDefined());
  await act(async () => {
    rememberMission(client, mission(3, '2026-10-14T00:01:00Z'));
  });
  await waitFor(() => expect(screen.getByText('3 legs')).toBeVisible());
  await act(async () => {
    release({ missions: [original], total: 1 });
  });
  await waitFor(() => expect(screen.queryByText('0 legs')).toBeNull());
  expect(screen.getByText('3 legs')).toBeVisible();
});
