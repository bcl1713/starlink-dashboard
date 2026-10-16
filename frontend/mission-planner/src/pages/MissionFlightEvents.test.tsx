// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, it, expect } from 'vitest';
import { MissionFlightEvents } from './MissionFlightEvents';
const { get, create } = vi.hoisted(() => ({ get: vi.fn(), create: vi.fn() }));
vi.mock('@/services/telemetry-archives', () => ({
  telemetryArchivesApi: { events: get, create },
}));

it('lets an operator create a missing observed event with a reason', async () => {
  get.mockResolvedValue({
    status: { movement_state: 'unknown', movement_uncertain: true },
    events: [],
    capture: {},
  });
  create.mockResolvedValue({});
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MissionFlightEvents
        missionId="m"
        legs={[{ id: 'l', name: 'First leg' }]}
      />
    </QueryClientProvider>
  );
  await screen.findByText(/Movement uncertain/);
  fireEvent.change(screen.getByLabelText('Observed time (UTC)'), {
    target: { value: '2026-01-01T00:00' },
  });
  fireEvent.change(screen.getByLabelText('Reason'), {
    target: { value: 'Crew confirmation' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Record event' }));
  await waitFor(() =>
    expect(create).toHaveBeenCalledWith(
      'm',
      'l',
      expect.objectContaining({
        kind: 'off_blocks',
        reason: 'Crew confirmation',
        occurred_at: '2026-01-01T00:00:00.000Z',
      })
    )
  );
});
