/** @vitest-environment jsdom */
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PlanningXDraft } from './PlanningXDraft';
import { routesApi } from '../../services/routes';
import type { ExpectedLeg, PlanningDraft } from '../../types/planning';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const leg: ExpectedLeg = {
  id: 'leg',
  ordinal: 1,
  departure_airport: 'AAA',
  arrival_airport: 'BBB',
  departure_time: '2026-10-25T12:00:00Z',
  arrival_time: '2026-10-25T13:00:00Z',
  route: {
    route_id: 'real',
    source_id: 's',
    content_hash: 'hash',
    filename: 'synthetic.kml',
  },
};
it('adds an ordered manual swap from a timed immutable occurrence preserving context and locks', async () => {
  vi.spyOn(routesApi, 'get').mockResolvedValue({
    id: 'real',
    name: 'Route',
    points: [
      {
        latitude: 1,
        longitude: 2,
        occurrence_id: 'actual-occurrence',
        expected_arrival_time: '2026-10-25T12:10:30Z',
      },
    ],
  });
  function Form() {
    const [draft, setDraft] = useState<PlanningDraft>({
      permitted_satellite_ids: ['X'],
      locks: [{ id: 'initial', kind: 'initial', target_satellite_id: 'X' }],
      evaluation_context: {
        input_identity: 'context',
        boundaries: ['2026-10-25T12:10:30Z'],
      },
    });
    return (
      <>
        <PlanningXDraft
          leg={leg}
          draft={draft}
          onChange={(updates) => setDraft({ ...draft, ...updates })}
          options={{
            satellites: [
              {
                id: 'X',
                label: 'X',
                eligible: true,
                transport: 'X',
                longitude: 10,
              },
            ],
          }}
        />
        <output>{JSON.stringify(draft)}</output>
      </>
    );
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Form />
    </QueryClientProvider>
  );
  await screen.findByRole('option', { name: /actual-occurrence/ });
  expect(screen.getByLabelText('Initial X-band satellite')).toBeDisabled();
  fireEvent.change(screen.getByLabelText('New swap route occurrence'), {
    target: { value: '0' },
  });
  fireEvent.change(screen.getByLabelText('New swap satellite'), {
    target: { value: 'X' },
  });
  fireEvent.click(screen.getByText('Add manual swap'));
  expect(screen.getByRole('status')).toHaveTextContent('"route_id":"real"');
  expect(screen.getByRole('status')).toHaveTextContent(
    '"occurrence_id":"actual-occurrence"'
  );
  expect(screen.getByRole('status')).toHaveTextContent(
    '"input_identity":"context"'
  );
  expect(screen.getByRole('status')).toHaveTextContent('"id":"initial"');
});
