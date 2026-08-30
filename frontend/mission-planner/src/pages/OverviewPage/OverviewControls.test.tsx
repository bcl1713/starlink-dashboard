import { fireEvent, render, screen, within } from '@testing-library/react';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import {
  addOverviewClock,
  createDefaultOverviewPreferences,
  type OverviewPreferences,
} from './preferences';
import { OverviewControls } from './OverviewControls';

function renderControls(
  preferences: OverviewPreferences = {
    ...createDefaultOverviewPreferences(),
    disclosures: {
      controlsExpanded: true,
      additionalClocksExpanded: false,
      clockSettingsExpanded: false,
    },
  },
  overrides: Partial<React.ComponentProps<typeof OverviewControls>> = {}
) {
  const props: React.ComponentProps<typeof OverviewControls> = {
    preferences,
    manualRefreshPending: false,
    onRefreshCadenceChange: vi.fn(),
    onManualRefresh: vi.fn(),
    onRadarEnabledChange: vi.fn(),
    onPOIFilterChange: vi.fn(),
    onControlsExpandedChange: vi.fn(),
    onClockSettingsExpandedChange: vi.fn(),
    onAddClock: vi.fn(),
    onRelabelClock: vi.fn(),
    onMoveClock: vi.fn(),
    onRemoveClock: vi.fn(),
    ...overrides,
  };
  const view = render(<OverviewControls {...props} />);
  return { ...view, props };
}

describe('OverviewControls', () => {
  it('renders one accessible controlled control set with exact options', () => {
    const { props } = renderControls();
    const disclosure = screen.getByRole('button', {
      name: 'Overview controls',
    });
    const region = document.getElementById(
      disclosure.getAttribute('aria-controls') ?? ''
    );

    expect(disclosure).toHaveAttribute('aria-expanded', 'true');
    expect(region).not.toBeNull();
    expect(
      screen.getByRole('combobox', { name: 'Refresh cadence' })
    ).toHaveValue('1');
    expect(
      within(screen.getByRole('combobox', { name: 'Refresh cadence' }))
        .getAllByRole('option')
        .map((option) => [option.textContent, option.getAttribute('value')])
    ).toEqual([
      ['1s', '1'],
      ['2s', '2'],
      ['5s', '5'],
      ['10s', '10'],
      ['30s', '30'],
      ['Paused', 'paused'],
    ]);
    expect(
      screen.getAllByRole('combobox', { name: 'POI category' })
    ).toHaveLength(1);
    expect(
      screen.getByRole('checkbox', { name: 'Weather radar' })
    ).toBeChecked();
    expect(screen.getByText('Radar on')).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Refresh overview' })
    ).toHaveClass('min-h-11');

    fireEvent.change(
      screen.getByRole('combobox', { name: 'Refresh cadence' }),
      {
        target: { value: '10' },
      }
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'POI category' }), {
      target: { value: 'alternate' },
    });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Weather radar' }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));

    expect(props.onRefreshCadenceChange).toHaveBeenCalledWith(10);
    expect(props.onPOIFilterChange).toHaveBeenCalledWith('alternate');
    expect(props.onRadarEnabledChange).toHaveBeenCalledWith(false);
    expect(props.onManualRefresh).toHaveBeenCalledTimes(1);
  });

  it('respects manual disabled state and controlled disclosure rerenders', () => {
    const { rerender, props } = renderControls(undefined, {
      manualRefreshPending: true,
    });
    const manual = screen.getByRole('button', { name: 'Refresh overview' });

    expect(manual).toBeDisabled();
    fireEvent.click(manual);
    expect(props.onManualRefresh).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Overview controls' }));
    expect(props.onControlsExpandedChange).toHaveBeenCalledWith(false);

    rerender(
      <OverviewControls
        {...props}
        manualRefreshPending={false}
        preferences={{
          ...props.preferences,
          disclosures: {
            ...props.preferences.disclosures,
            controlsExpanded: true,
            clockSettingsExpanded: true,
          },
        }}
      />
    );
    expect(
      screen.getByRole('button', { name: 'Overview controls' })
    ).toHaveAttribute('aria-expanded', 'true');
    expect(
      screen.getByRole('button', { name: 'Clock settings' })
    ).toHaveAttribute('aria-expanded', 'true');
  });

  it('validates add clock input before emitting callbacks', () => {
    const { props } = renderControls({
      ...createDefaultOverviewPreferences(),
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: false,
        clockSettingsExpanded: true,
      },
    });

    fireEvent.change(screen.getByLabelText('Clock time zone'), {
      target: { value: 'Europe/London' },
    });
    fireEvent.change(screen.getByLabelText('Clock label'), {
      target: { value: ' London ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add clock' }));
    expect(props.onAddClock).toHaveBeenCalledWith({
      timeZone: 'Europe/London',
      label: 'London',
    });

    fireEvent.change(screen.getByLabelText('Clock time zone'), {
      target: { value: 'Etc/UTC' },
    });
    fireEvent.change(screen.getByLabelText('Clock label'), {
      target: { value: 'Zulu' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add clock' }));
    expect(screen.getByText('Clock already exists.')).toBeVisible();
    expect(props.onAddClock).toHaveBeenCalledTimes(1);
  });

  it('renders clock edit actions with UTC restrictions and add limit', () => {
    let preferences = createDefaultOverviewPreferences();
    for (const [timeZone, label] of [
      ['Europe/London', 'London'],
      ['America/Los_Angeles', 'LA'],
      ['America/Denver', 'Denver'],
      ['America/Phoenix', 'Phoenix'],
    ] as const) {
      preferences = addOverviewClock(preferences, { timeZone, label });
    }
    preferences = {
      ...preferences,
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: false,
        clockSettingsExpanded: true,
      },
    };
    const { props } = renderControls(preferences);

    expect(screen.getByText('UTC is always shown first.')).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Remove UTC (Zulu)' })
    ).toBeNull();
    expect(screen.getByRole('button', { name: 'Add clock' })).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Move Washington DC up' })
    ).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Relabel Tokyo'), {
      target: { value: ' Tokyo Prime ' },
    });
    fireEvent.blur(screen.getByLabelText('Relabel Tokyo'));
    fireEvent.click(screen.getByRole('button', { name: 'Move Tokyo down' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove Tokyo' }));
    expect(props.onRelabelClock).toHaveBeenCalledWith(
      'tz:Asia/Tokyo',
      'Tokyo Prime'
    );
    expect(props.onMoveClock).toHaveBeenCalledWith('tz:Asia/Tokyo', 'down');
    expect(props.onRemoveClock).toHaveBeenCalledWith('tz:Asia/Tokyo');
  });
});
