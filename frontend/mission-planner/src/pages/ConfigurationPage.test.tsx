/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
vi.mock('@/hooks/api/useOverviewClockSettings', () => ({
  useOverviewClockSettings: vi.fn(),
}));
vi.mock('@/hooks/api/useUpdateOverviewClockSettings', () => ({
  useUpdateOverviewClockSettings: vi.fn(),
}));
vi.mock('../components/gps/GPSControlCard', () => ({
  GPSControlCard: () => null,
}));
import { useOverviewClockSettings } from '@/hooks/api/useOverviewClockSettings';
import { useUpdateOverviewClockSettings } from '@/hooks/api/useUpdateOverviewClockSettings';
import { ConfigurationPage } from './ConfigurationPage';
afterEach(() => {
  cleanup();
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
  it('renders the clock editor fields', () => {
    mockLoadedClockSettings();
    vi.mocked(useUpdateOverviewClockSettings).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as never);
    render(<ConfigurationPage />);
    expect(screen.getByLabelText('Clock 1 label')).not.toBeNull();
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

    expect(screen.getByRole('status')).not.toBeNull();
    expect(screen.getByText('Loading operational clocks...')).not.toBeNull();
  });
});
