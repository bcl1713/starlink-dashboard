/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { OperatorWorkspace } from './OperatorWorkspace';
import { OperatorWorkspaceProvider } from './OperatorWorkspaceProvider';
import { DraftRegistry } from './draftRegistry';
import * as api from '@/services/operator';
import { health } from '@/test/operator-fixtures';
const missionState = vi.hoisted(() => ({ pending: false }));
vi.mock('@/hooks/api/useMissions', () => ({
  useMission: () => ({ data: undefined, isPending: missionState.pending }),
  useMissionsPage: () => ({ data: { missions: [] } }),
}));
const clients: QueryClient[] = [];
afterEach(() => {
  missionState.pending = false;
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  sessionStorage.clear();
  localStorage.clear();
  vi.restoreAllMocks();
});
function mount(route = '/operator?workspace=1') {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
    ready: false,
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <OperatorWorkspaceProvider registry={new DraftRegistry(sessionStorage)}>
          <OperatorWorkspace />
        </OperatorWorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
it('renders a cold workspace before any training context or checked evidence exists', () => {
  mount();
  expect(screen.getByRole('button', { name: 'Help' })).toBeTruthy();
  expect(
    screen.getByRole('heading', { name: 'Choose a mission' })
  ).toBeTruthy();
});
it('explains separate nonproduction setup instead of opening training in an ordinary instance', () => {
  mount();
  fireEvent.click(screen.getByRole('button', { name: 'Help' }));
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guided mission walkthrough',
    })
  );
  expect(
    screen.getByText(/Training requires a separate private instance/)
  ).toBeTruthy();
  expect(
    screen.queryByRole('complementary', { name: 'Guided mission walkthrough' })
  ).toBeNull();
});

it('waits for selected mission identity before enabling the guide launcher', () => {
  missionState.pending = true;
  mount('/operator?workspace=1&mission_id=loading-private-mission');
  fireEvent.click(screen.getByRole('button', { name: 'Help' }));
  const button = screen.getByRole('button', {
    name: 'Guided mission walkthrough',
  }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(
    screen.getByText(
      'Checking the selected mission and private training identity…'
    )
  ).toBeTruthy();
});
