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
import { ImportDialog } from './ImportDialog';
import { itineraryImportApi } from '../../services/itinerary-import';
vi.mock('../../services/itinerary-import', () => ({
  itineraryImportApi: {
    start: vi.fn(),
    read: vi.fn(),
    cancel: vi.fn(),
    resolve: vi.fn(),
    commit: vi.fn(),
  },
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});
const operation = {
  id: 'operation',
  generation: 1,
  state: 'committed',
  stage: 'complete',
  mission_id: 'ordinary',
  revision: false,
  deadline: '2035-01-01T12:00:00Z',
  issues: [],
  details: {},
  error: null,
};
function setup(missionId?: string) {
  const done = vi.fn();
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <ImportDialog
        open
        onClose={() => {}}
        onSuccess={done}
        missionId={missionId}
      />
    </QueryClientProvider>
  );
  return done;
}
it('uploads all files once and opens an ordinary mission without intermediate reviews', async () => {
  vi.mocked(itineraryImportApi.start).mockResolvedValue(operation as never);
  const done = setup();
  fireEvent.change(screen.getByLabelText('Itinerary PDF'), {
    target: { files: [new File(['pdf'], 'itinerary.pdf')] },
  });
  fireEvent.change(screen.getByLabelText('Route KMLs'), {
    target: {
      files: [new File(['k1'], 'one.kml'), new File(['k2'], 'two.kml')],
    },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Generate mission' }));
  await waitFor(() => expect(done).toHaveBeenCalledWith('ordinary'));
  expect(vi.mocked(itineraryImportApi.start).mock.calls[0][1]).toHaveLength(2);
  expect(screen.queryByText('Confirm access')).not.toBeInTheDocument();
});
it('resumes persisted work on reopen', async () => {
  localStorage.setItem('itinerary-import:new', 'operation');
  vi.mocked(itineraryImportApi.read).mockResolvedValue(operation as never);
  const done = setup();
  await waitFor(() => expect(done).toHaveBeenCalledWith('ordinary'));
  expect(itineraryImportApi.start).not.toHaveBeenCalled();
});
it('shows only unresolved route corrections', async () => {
  localStorage.setItem('itinerary-import:new', 'operation');
  vi.mocked(itineraryImportApi.read).mockResolvedValue({
    ...operation,
    state: 'needs_input',
    issues: [
      {
        code: 'route_association_unresolved',
        leg_id: 'l',
        message: 'Choose route',
        candidates: ['r'],
      },
    ],
    details: {
      itinerary: {
        name: 'M',
        expected_legs: [
          {
            id: 'l',
            ordinal: 1,
            departure_airport: 'AAAA',
            arrival_airport: 'BBBB',
            departure_time: '2035-01-01T10:00:00Z',
            arrival_time: '2035-01-01T11:00:00Z',
            ar_rows: [],
            ar_section_status: 'empty',
          },
        ],
      },
      routes: [{ id: 'r', name: 'leg.kml' }],
    },
  } as never);
  setup();
  expect(await screen.findByLabelText('Route for leg 1')).toBeVisible();
  expect(
    screen.queryByRole('checkbox', { name: /access/i })
  ).not.toBeInTheDocument();
});
it('automatically accepts a revision without showing JSON review', async () => {
  localStorage.setItem('itinerary-import:m', 'operation');
  vi.mocked(itineraryImportApi.read).mockResolvedValue({
    ...operation,
    state: 'ready',
    revision: true,
    details: {
      revision: { changes: ['legs.l.adjusted_departure_time'], conflicts: [] },
    },
  } as never);
  vi.mocked(itineraryImportApi.commit).mockResolvedValue(operation as never);
  const done = setup('m');
  expect(
    screen.queryByRole('button', { name: 'Apply revision' })
  ).not.toBeInTheDocument();
  await waitFor(() => expect(done).toHaveBeenCalledWith('ordinary'));
});

it('resumes an unfinished revision using retained sources without another upload', async () => {
  vi.mocked(itineraryImportApi.start).mockResolvedValue({
    ...operation,
    state: 'queued',
    revision: true,
  } as never);
  setup('ordinary');
  const prepare = screen.getByRole('button', { name: 'Update mission' });
  expect(prepare).toBeEnabled();
  fireEvent.click(prepare);
  await waitFor(() =>
    expect(itineraryImportApi.start).toHaveBeenCalledWith(
      null,
      [],
      expect.any(String),
      'ordinary'
    )
  );
});
