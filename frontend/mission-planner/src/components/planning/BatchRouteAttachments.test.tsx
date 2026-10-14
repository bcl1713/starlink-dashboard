/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { BatchRouteAttachments } from './BatchRouteAttachments';
import { planningApi } from '../../services/planning';
import type { BatchRoutePreview, PlanningView } from '../../types/planning';
const view = {
  mission: { id: 'm', legs: [] },
  revision: 1,
  expected_legs: [
    {
      leg: {
        id: 'a',
        ordinal: 1,
        departure_airport: 'AAA',
        arrival_airport: 'BBB',
      },
      input_identity: 'hash',
    },
    {
      leg: {
        id: 'b',
        ordinal: 2,
        departure_airport: 'BBB',
        arrival_airport: 'AAA',
      },
      input_identity: 'other',
    },
  ],
} as unknown as PlanningView;
const preview: BatchRoutePreview = {
  preview_id: 'batch',
  expected_revision: 1,
  expires_at: '2030-01-01T00:00:00Z',
  attachments: [
    {
      attachment_id: 'one',
      filename: 'misleading.kml',
      source_departure_time: '2026-10-25T11:00:00Z',
      source_arrival_time: '2026-10-25T12:00:00Z',
      content_hash: 'a',
      suggested_leg_id: null,
      errors: [],
      candidates: [
        {
          leg_id: 'a',
          reasons: ['airports_match'],
          discrepancy_errors: [
            { code: 'route_time_discrepancy', message: 'UTC windows differ' },
          ],
        },
        { leg_id: 'b', reasons: ['airports_match'], discrepancy_errors: [] },
      ],
    },
  ],
};
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function setup(staged = preview) {
  const client = new QueryClient();
  client.setQueryData(['planning', 'm'], view);
  vi.spyOn(planningApi, 'previewRoutes').mockResolvedValue(staged);
  vi.spyOn(planningApi, 'discardRoutes').mockResolvedValue();
  const accepted = vi
    .spyOn(planningApi, 'acceptRoutes')
    .mockResolvedValue({ ...view, revision: 2 });
  const receive = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <BatchRouteAttachments view={view} onAccepted={receive} />
    </QueryClientProvider>
  );
  fireEvent.change(screen.getByLabelText('Route KMLs'), {
    target: { files: [new File(['one'], 'misleading.kml')] },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Preview route attachments' })
  );
  return { accepted, receive };
}
it('requires a visible assignment for ambiguity and each discrepancy acknowledgment', async () => {
  const { accepted, receive } = setup();
  const choose = await screen.findByLabelText('Assign misleading.kml');
  expect(screen.getByText(/Source UTC 2026-10-25T11:00:00Z/)).toBeVisible();
  expect(choose).toHaveValue('');
  expect(
    screen.getByRole('button', { name: 'Accept route bindings' })
  ).toBeDisabled();
  fireEvent.change(choose, { target: { value: 'a' } });
  expect(screen.getByText('UTC windows differ')).toBeVisible();
  expect(
    screen.getByRole('button', { name: 'Accept route bindings' })
  ).toBeDisabled();
  fireEvent.click(
    screen.getByLabelText('Acknowledge misleading.kml: UTC windows differ')
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Accept route bindings' })
  );
  await waitFor(() => expect(receive).toHaveBeenCalled());
  expect(accepted.mock.calls[0][1]).toEqual({
    preview_id: 'batch',
    expected_revision: 1,
    assignments: [
      {
        attachment_id: 'one',
        leg_id: 'a',
        discrepancy_acknowledgments: ['route_time_discrepancy'],
      },
    ],
  });
});
it('keeps errors visible and discards only its owned staged batch', async () => {
  setup({
    ...preview,
    attachments: [
      ...preview.attachments,
      {
        attachment_id: 'bad',
        filename: 'invalid.kml',
        content_hash: 'b',
        suggested_leg_id: null,
        candidates: [],
        errors: [{ code: 'invalid', message: 'Replace this KML' }],
      },
    ],
  });
  expect(await screen.findByText('Replace this KML')).toBeVisible();
  expect(screen.getByLabelText('Assign invalid.kml')).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Discard staged attachments' })
  );
  await waitFor(() =>
    expect(planningApi.discardRoutes).toHaveBeenCalledWith('m', 'batch')
  );
  expect(planningApi.acceptRoutes).not.toHaveBeenCalled();
});
it('prefills unique evidence but blocks two files targeting the same leg', async () => {
  setup({
    ...preview,
    attachments: [
      { ...preview.attachments[0], suggested_leg_id: 'b' },
      {
        ...preview.attachments[0],
        attachment_id: 'two',
        filename: 'second.kml',
        suggested_leg_id: 'b',
      },
    ],
  });
  expect(await screen.findByLabelText('Assign second.kml')).toHaveValue('b');
  expect(
    screen.getByRole('button', { name: 'Accept route bindings' })
  ).toBeDisabled();
  expect(screen.getByText(/Choose one attachment per leg/)).toBeVisible();
});
