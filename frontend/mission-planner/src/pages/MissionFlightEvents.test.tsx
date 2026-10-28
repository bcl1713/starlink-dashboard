import { enterZulu } from '@/test/utc-controls';
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, it, expect, beforeEach, afterEach } from 'vitest';
import { MissionFlightEvents } from './MissionFlightEvents';
const { get, create, health } = vi.hoisted(() => ({
  get: vi.fn(),
  create: vi.fn(),
  health: vi.fn(),
}));
vi.mock('@/services/telemetry-archives', () => ({
  telemetryArchivesApi: { events: get, create, health },
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
  enterZulu('Observed time', '2026-01-01T00:00');
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

afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
  health.mockResolvedValue({
    state: 'ready',
    mode: 'live',
    detection_available: true,
    recording_available: true,
    history_available: true,
  });
});

function renderPanel() {
  return render(
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
}

it('explains storage recovery without implying that selecting live fixes it', async () => {
  get.mockRejectedValue(new Error('unavailable'));
  health.mockResolvedValue({
    state: 'retrying',
    mode: 'live',
    detection_available: false,
    recording_available: false,
    history_available: false,
    message: 'Check flight archive directory permissions.',
    retry_in_seconds: 5,
  });
  renderPanel();
  await screen.findByText(/Automatic landing detection unavailable/);
  expect(
    screen.getByText(/Check flight archive directory permissions/)
  ).toBeVisible();
  expect(screen.getByText(/Automatic retry in 5/)).toBeVisible();
  expect(
    screen.queryByText(/Recording controls require live mode/)
  ).not.toBeInTheDocument();
});

it('discloses failed capture while keeping detector and manual corrections available', async () => {
  get.mockResolvedValue({
    status: { movement_state: 'taxi_in', movement_uncertain: false },
    capture: {},
    events: [],
  });
  health.mockResolvedValue({
    state: 'degraded',
    mode: 'live',
    detection_available: true,
    recording_available: false,
    history_available: true,
    message: 'Check available storage.',
  });
  renderPanel();
  await screen.findByText(/Telemetry recording unavailable/);
  expect(screen.getByText(/Movement: taxi in/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Record event' })).toBeEnabled();
});

it('labels retained history during simulation and shows estimated and confirmation times', async () => {
  health.mockResolvedValue({
    state: 'inactive',
    mode: 'simulation',
    detection_available: false,
    recording_available: false,
    history_available: true,
  });
  get.mockResolvedValue({
    status: { movement_state: 'taxi_in', movement_uncertain: false },
    capture: {},
    events: [
      {
        event_id: 'one',
        kind: 'landed',
        occurred_at: '2026-01-01T00:00:00Z',
        detected_at: '2026-01-01T00:00:20Z',
        source: 'inferred',
      },
    ],
  });
  renderPanel();
  await screen.findByText(/Live recording paused in simulation/);
  expect(screen.getByText(/Estimated landing/)).toBeVisible();
  expect(screen.getByText(/confirmed 2026-01-01T00:00:20Z/)).toBeVisible();
});
