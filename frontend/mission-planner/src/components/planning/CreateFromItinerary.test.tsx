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
    screen.getByText(/Attach routes before reviewing AR occurrences/)
  ).toBeVisible();
  fireEvent.change(screen.getByLabelText('Mission name'), {
    target: { value: 'Corrected name' },
  });
  expect(screen.queryByLabelText(/confirm no AR windows/i)).toBeNull();
  fireEvent.click(
    screen.getByRole('button', { name: 'Continue to route attachments' })
  );
  await screen.findByRole('group', { name: 'Batch route attachments' });
  expect(done).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Continue to source review' })
  );
  await waitFor(() => expect(done).toHaveBeenCalledWith('created'));
  expect(create.mock.calls[0][0]).toMatchObject({
    itinerary: {
      name: 'Corrected name',
      expected_legs: [{ id: 'stable', draft: { no_ars_confirmed: false } }],
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

it('collects PDF and KML batch before route-dependent review', async () => {
  vi.spyOn(planningApi, 'previewItinerary').mockResolvedValue({
    preview_id: 'p',
    parsed_values: itinerary,
    field_errors: [{ code: 'source', message: 'Correct source UTC row' }],
    expires_at: '2030-01-01T00:00:00Z',
  });
  vi.spyOn(planningApi, 'create').mockResolvedValue({
    mission: { id: 'created', legs: [] },
    revision: 1,
    expected_legs: itinerary.expected_legs.map((leg) => ({
      leg,
      input_identity: 'identity',
      review_status: 'awaiting_kml',
    })),
  } as never);
  const preview = vi.spyOn(planningApi, 'previewRoutes').mockResolvedValue({
    preview_id: 'batch',
    expected_revision: 1,
    expires_at: '2030-01-01T00:00:00Z',
    attachments: [
      {
        attachment_id: 'route',
        filename: 'route.kml',
        content_hash: 'hash',
        suggested_leg_id: 'stable',
        errors: [],
        candidates: [
          {
            leg_id: 'stable',
            reasons: ['airports_match', 'utc_window_matches'],
            discrepancy_errors: [],
          },
        ],
      },
    ],
  });
  setup();
  const route = new File(['route'], 'route.kml');
  fireEvent.change(screen.getByLabelText('Itinerary PDF'), {
    target: { files: [new File(['pdf'], 'itinerary.pdf')] },
  });
  fireEvent.change(screen.getByLabelText('Initial route KMLs'), {
    target: { files: [route] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Extract itinerary' }));
  await screen.findByText(/Correct source UTC row/);
  expect(screen.queryByLabelText(/Confirm AR/)).toBeNull();
  fireEvent.click(
    screen.getByRole('button', { name: 'Continue to route attachments' })
  );
  expect(await screen.findByLabelText('Assign route.kml')).toHaveValue(
    'stable'
  );
  expect(preview).toHaveBeenCalledWith('created', [route], 1);
});

it('overrides only new unlabeled AR units while preserving declared feet', async () => {
  const rows = [
    {
      id: 'default',
      track: 'DEFAULT',
      entry_time: '2026-10-25T12:10:00Z',
      exit_time: '2026-10-25T12:20:00Z',
      source_time_precision: 'minute' as const,
      source_altitude: 200,
      confirmed_units: 'flight_level' as const,
      unit_origin: 'import_default' as const,
    },
    {
      id: 'declared',
      track: 'DECLARED',
      entry_time: '2026-10-25T12:30:00Z',
      exit_time: '2026-10-25T12:40:00Z',
      source_time_precision: 'minute' as const,
      source_altitude: 20000,
      confirmed_units: 'feet' as const,
      unit_origin: 'source_declared' as const,
    },
  ];
  vi.spyOn(planningApi, 'previewItinerary').mockResolvedValue({
    preview_id: 'p',
    expires_at: '2030-01-01T00:00:00Z',
    parsed_values: {
      ...itinerary,
      expected_legs: [
        {
          ...itinerary.expected_legs[0],
          ar_rows: rows,
          ar_section_status: 'listed',
        },
      ],
    },
  });
  const create = vi.spyOn(planningApi, 'create').mockResolvedValue({
    mission: { id: 'created', legs: [] },
    revision: 1,
    expected_legs: [],
  } as never);
  setup();
  fireEvent.change(screen.getByLabelText('Itinerary PDF'), {
    target: { files: [new File(['pdf'], 'itinerary.pdf')] },
  });
  fireEvent.click(screen.getByText('Extract itinerary'));
  expect(await screen.findByText('DEFAULT: FL200')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Unlabeled AR altitude units'), {
    target: { value: 'meters' },
  });
  fireEvent.click(screen.getByText('Continue to route attachments'));
  await waitFor(() => expect(create).toHaveBeenCalled());
  expect(
    create.mock.calls[0][0].itinerary.expected_legs?.[0].ar_rows
  ).toMatchObject([
    {
      confirmed_units: 'meters',
      unit_origin: 'operator_override',
      confirmed: false,
    },
    { confirmed_units: 'feet', unit_origin: 'source_declared' },
  ]);
});

it('preserves unresolved units from a blocked altitude-column declaration', async () => {
  vi.spyOn(planningApi, 'previewItinerary').mockResolvedValue({
    preview_id: 'blocked',
    parsed_values: {
      ...itinerary,
      expected_legs: [
        {
          ...itinerary.expected_legs[0],
          ar_section_status: 'unrecognized',
          ar_rows: [
            {
              id: 'row',
              track: 'UNSUPPORTED',
              source_altitude: 210,
              confirmed_units: null,
              unit_origin: null,
              entry_time: '2026-10-25T12:10:00Z',
              exit_time: '2026-10-25T12:20:00Z',
            },
          ],
        },
      ],
    },
    field_errors: [
      { code: 'altitude_units_unknown', message: 'Unsupported km units' },
    ],
    expires_at: '2026-10-26T12:00:00Z',
  } as never);
  const create = vi.spyOn(planningApi, 'create').mockResolvedValue({
    mission: { id: 'created', legs: [] },
    revision: 1,
    expected_legs: [],
  } as never);
  setup();
  fireEvent.change(screen.getByLabelText('Itinerary PDF'), {
    target: { files: [new File(['source'], 'units.pdf')] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Extract itinerary' }));
  await screen.findByLabelText('Mission name');
  expect(screen.getByText('UNSUPPORTED: 210 units required')).toBeVisible();
  fireEvent.click(
    screen.getByRole('button', { name: 'Continue to route attachments' })
  );
  await waitFor(() => expect(create).toHaveBeenCalledOnce());
  expect(
    create.mock.calls[0][0].itinerary.expected_legs?.[0].ar_rows?.[0]
      .confirmed_units
  ).toBeNull();
});
