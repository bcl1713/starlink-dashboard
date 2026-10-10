/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CreateFromItinerary } from './CreateFromItinerary';
import { planningApi } from '../../services/planning';
vi.mock('../common/RouteMap', () => ({ RouteMap: () => null }));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const itinerary = {
  name: 'Synthetic rotated',
  aircraft: 'Test aircraft',
  call_sign: 'TEST',
  expected_legs: [
    {
      id: 'stable',
      ordinal: 1,
      departure_airport: 'AAA',
      arrival_airport: 'BBB',
      departure_time: '2026-10-25T12:00:00Z',
      arrival_time: '2026-10-25T13:00:00Z',
      ar_rows: [],
      ar_section_status: 'empty' as const,
    },
  ],
};
function setup() {
  vi.spyOn(planningApi, 'satelliteOptions').mockResolvedValue({
    satellites: [],
  });
  const done = vi.fn();
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <CreateFromItinerary open onClose={() => {}} onSuccess={done} />
    </QueryClientProvider>
  );
  return done;
}
it('corrects extraction and creates expected cards without requiring a permitted set', async () => {
  vi.spyOn(planningApi, 'previewItinerary').mockResolvedValue({
    preview_id: 'preview',
    parsed_values: itinerary,
    field_errors: [],
    expires_at: '2026-10-26T12:00:00Z',
  });
  const create = vi.spyOn(planningApi, 'create').mockResolvedValue({
    mission: { id: 'created', legs: [] },
    revision: 1,
    expected_legs: [],
  } as never);
  const done = setup();
  fireEvent.change(screen.getByLabelText('Itinerary PDF'), {
    target: { files: [new File(['synthetic'], 'rotated.pdf')] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Extract itinerary' }));
  await screen.findByLabelText('Mission name');
  expect(
    screen.getByText(
      /Review AR windows and satellite access, generate and compare a proposal, then save the reviewed plan/
    )
  ).toBeVisible();
  fireEvent.change(screen.getByLabelText('Mission name'), {
    target: { value: 'Corrected name' },
  });
  fireEvent.click(screen.getByLabelText(/confirm no AR windows/i));
  fireEvent.click(
    screen.getByRole('button', { name: 'Confirm itinerary and create draft' })
  );
  await waitFor(() => expect(done).toHaveBeenCalledWith('created'));
  expect(create.mock.calls[0][0]).toMatchObject({
    itinerary: {
      name: 'Corrected name',
      expected_legs: [{ id: 'stable', draft: { no_ars_confirmed: true } }],
    },
    permitted_satellite_ids: [],
    starshield_enabled: true,
  });
  expect(create.mock.calls[0][0]).not.toHaveProperty('expected_revision');
});
it('retains the selected PDF and corrections after an extraction failure', async () => {
  vi.spyOn(planningApi, 'previewItinerary')
    .mockResolvedValueOnce({
      preview_id: 'p',
      parsed_values: itinerary,
      expires_at: '2026-10-26T12:00:00Z',
    })
    .mockRejectedValueOnce(new Error('Unreadable PDF'));
  setup();
  const file = new File(['synthetic'], 'rotated.pdf');
  fireEvent.change(screen.getByLabelText('Itinerary PDF'), {
    target: { files: [file] },
  });
  fireEvent.click(screen.getByText('Extract itinerary'));
  await screen.findByLabelText('Mission name');
  fireEvent.change(screen.getByLabelText('Mission name'), {
    target: { value: 'Kept correction' },
  });
  fireEvent.click(screen.getByText('Extract itinerary'));
  await screen.findByText('Unreadable PDF');
  expect(screen.getByLabelText('Mission name')).toHaveValue('Kept correction');
  expect(
    (screen.getByLabelText('Itinerary PDF') as HTMLInputElement).files?.[0]
  ).toBe(file);
});
