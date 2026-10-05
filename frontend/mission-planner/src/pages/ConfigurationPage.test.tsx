/** @vitest-environment jsdom */
import {
  cleanup,
  fireEvent,
  render as renderTesting,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
const queryClients: QueryClient[] = [];
function render(element: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  queryClients.push(client);
  return renderTesting(
    <QueryClientProvider client={client}>{element}</QueryClientProvider>
  );
}
vi.mock('@/hooks/useOverviewAdsbLayer', () => ({
  useOverviewAdsbLayer: () => ({
    settings: undefined,
    contacts: [],
    sources: [],
    settingsError: false,
    trafficError: false,
  }),
}));
vi.mock('@/hooks/useConfigurationAdsbLayer', () => ({
  useConfigurationAdsbLayer: () => ({
    settings: undefined,
    contacts: [],
    contextContacts: [],
    settingsError: false,
    trafficError: false,
    sourceErrors: [],
  }),
}));
vi.mock('@/services/orbital-catalog', () => ({
  orbitalCatalogApi: {
    status: vi.fn().mockResolvedValue({
      status: 'loading',
      eligible_count: 0,
      rejected_count: 0,
      truncated_count: 0,
    }),
    resume: vi.fn(),
  },
}));

vi.mock('@/hooks/api/useOverviewHistorySettings', () => ({
  useOverviewHistorySettings: () => ({ data: { window_seconds: 300 } }),
}));
vi.mock('@/hooks/api/useUpdateOverviewHistorySettings', () => ({
  useUpdateOverviewHistorySettings: () => ({ mutate: vi.fn() }),
}));
vi.mock('@/hooks/api/useStatus', () => ({ useStatus: () => ({}) }));
vi.mock('@/hooks/api/useOverviewHistory', () => ({
  useOverviewHistory: () => ({}),
}));
vi.mock('@/hooks/api/useSatellites', () => ({ useSatellites: () => ({}) }));
vi.mock('@/hooks/api/useActiveXLink', () => ({ useActiveXLink: () => ({}) }));
vi.mock('@/hooks/api/useOverviewClockSettings', () => ({
  useOverviewClockSettings: vi.fn(),
}));
vi.mock('@/hooks/api/useUpdateOverviewClockSettings', () => ({
  useUpdateOverviewClockSettings: vi.fn(),
}));
vi.mock('@/hooks/api/useOverviewLinkSettings', () => ({
  useOverviewLinkSettings: () => ({
    data: {
      starshield_link_enabled: false,
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
      aircraft_history_enabled: true,
    },
  }),
}));
vi.mock('@/hooks/api/useUpdateOverviewLinkSettings', () => ({
  useUpdateOverviewLinkSettings: () => ({ mutate: vi.fn() }),
}));
vi.mock('../components/gps/GPSControlCard', () => ({
  GPSControlCard: () => (
    <div role="region" aria-label="GPS Configuration">
      GPS
    </div>
  ),
}));
import { useOverviewClockSettings } from '@/hooks/api/useOverviewClockSettings';
import { useUpdateOverviewClockSettings } from '@/hooks/api/useUpdateOverviewClockSettings';
import { ConfigurationPage } from './ConfigurationPage';
afterEach(() => {
  cleanup();
  queryClients.splice(0).forEach((client) => client.clear());
});

const clocks = [
  { label: 'Zulu / UTC', time_zone: 'UTC' },
  {
    label: 'Washington, DC',
    time_zone: 'America/New_York',
  },
  { label: 'Omaha, NE', time_zone: 'America/Chicago' },
  { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
];

function mockLoadedClockSettings() {
  vi.mocked(useOverviewClockSettings).mockReturnValue({
    data: { clocks },
    isError: false,
    isLoading: false,
  } as never);
}

describe('ConfigurationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it('keeps Overview settings reachable when clock settings fail', () => {
    vi.mocked(useOverviewClockSettings).mockReturnValue({
      isError: true,
    } as never);
    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      mutate: vi.fn(),
    } as never);
    render(<ConfigurationPage />);
    expect(screen.getByLabelText('Overview history window')).not.toBeNull();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Aircraft Traffic' }));
    expect(
      screen.getByRole('region', { name: 'ADS-B aircraft settings' })
    ).not.toBeNull();

    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Network Traffic' }));
    expect(
      screen.getByRole('switch', { name: 'Orbital traffic view' })
    ).not.toBeNull();
    expect(
      screen.getByRole('switch', { name: 'Starshield data link' })
    ).not.toBeNull();
    expect(
      screen.getByRole('switch', { name: 'X-band data link' })
    ).not.toBeNull();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Displays' }));
    expect(
      screen.getByRole('button', { name: 'Open Overview' })
    ).not.toBeNull();
    expect(
      screen.getByRole('button', { name: 'Recenter view' })
    ).not.toBeNull();
    expect(screen.queryByRole('button', { name: 'Fullscreen' })).toBeNull();
    expect(
      screen.queryByRole('region', { name: 'GPS Configuration' })
    ).toBeNull();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Terminal Controls' }));
    expect(
      screen.getByRole('region', { name: 'GPS Configuration' })
    ).not.toBeNull();
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Diagnostics' }));
    expect(
      screen.getByRole('region', { name: 'Orbital traffic diagnostics' })
    ).not.toBeNull();
    expect(
      screen.getByRole('region', { name: 'Overview map diagnostics' })
    ).not.toBeNull();
    expect(
      screen.getByRole('region', { name: 'ADS-B source status' })
    ).not.toBeNull();
  });
  it('renders the clock editor fields', () => {
    mockLoadedClockSettings();
    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as never);
    render(<ConfigurationPage />);
    expect(screen.getByLabelText('Clock 1 label')).not.toBeNull();
  });

  it('shows a save-specific alert when the loaded settings fail to update', () => {
    mockLoadedClockSettings();
    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      isError: true,
      isPending: false,
      mutate: vi.fn(),
    } as never);

    render(<ConfigurationPage />);

    expect(screen.getByLabelText('Clock 1 label')).not.toBeNull();
    expect(screen.getByRole('alert')).not.toBeNull();
    expect(
      screen.getByText('Unable to save operational clocks. Please try again.')
    ).not.toBeNull();
  });

  it('forwards edited clock settings to the update mutation', () => {
    const mutate = vi.fn();
    mockLoadedClockSettings();
    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      mutate,
      isPending: false,
    } as never);
    render(<ConfigurationPage />);
    const labelInput = screen.getByLabelText(
      'Clock 3 label'
    ) as HTMLInputElement;
    fireEvent.change(labelInput, {
      target: { value: 'Zulu Custom' },
    });
    const submitButton = screen.getByRole('button', {
      name: 'Save operational clocks',
    });
    fireEvent.click(submitButton);
    expect(mutate).toHaveBeenCalledWith({
      clocks: [
        { label: 'Zulu / UTC', time_zone: 'UTC' },
        {
          label: 'Washington, DC',
          time_zone: 'America/New_York',
        },
        { label: 'Zulu Custom', time_zone: 'America/Chicago' },
        { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
      ],
    });
  });

  it('renders alert on error', () => {
    vi.mocked(useOverviewClockSettings).mockReturnValue({
      data: undefined,
      isError: true,
      isLoading: false,
    } as never);

    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as never);

    render(<ConfigurationPage />);

    expect(screen.getByRole('alert')).not.toBeNull();
    expect(screen.getByText('Operational clocks unavailable')).not.toBeNull();
  });

  it('renders status on loading', () => {
    vi.mocked(useOverviewClockSettings).mockReturnValue({
      data: undefined,
      isError: false,
      isLoading: true,
    } as never);

    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as never);

    render(<ConfigurationPage />);

    expect(screen.getAllByRole('status')).toContain(
      screen.getByText('Loading operational clocks...')
    );
    expect(screen.getByText('Loading operational clocks...')).not.toBeNull();
  });
});

describe('Overview camera preference', () => {
  it('defaults following off and retains explicit opt-in across Configuration mounts', () => {
    localStorage.clear();
    mockLoadedClockSettings();
    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      mutate: vi.fn(),
    } as never);
    const first = render(<ConfigurationPage />);
    const follow = screen.getByRole('switch', {
      name: 'Follow aircraft on Overview',
    }) as HTMLInputElement;
    expect(follow.checked).toBe(false);
    fireEvent.click(follow);
    expect(follow.checked).toBe(true);
    first.unmount();
    render(<ConfigurationPage />);
    expect(
      (
        screen.getByRole('switch', {
          name: 'Follow aircraft on Overview',
        }) as HTMLInputElement
      ).checked
    ).toBe(true);
    localStorage.clear();
  });
});

it('keeps unsaved clock edits when navigating between configuration sections', () => {
  mockLoadedClockSettings();
  vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
    mutate: vi.fn(),
  } as never);
  render(<ConfigurationPage />);
  fireEvent.change(screen.getByLabelText('Clock 1 label'), {
    target: { value: 'Unsaved label' },
  });
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'Aircraft Traffic' }));
  expect(
    screen.queryByRole('button', { name: 'Save operational clocks' })
  ).toBeNull();
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'Overview' }));
  expect(
    (screen.getByLabelText('Clock 1 label') as HTMLInputElement).value
  ).toBe('Unsaved label');
});
