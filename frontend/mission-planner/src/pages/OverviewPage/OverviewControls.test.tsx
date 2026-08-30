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
      within(screen.getByRole('combobox', { name: 'POI category' }))
        .getAllByRole('option')
        .map((option) => [option.textContent, option.getAttribute('value')])
    ).toEqual([
      ['Departure & Arrival', 'departure,arrival'],
      ['All POIs', ''],
      ['Departure Only', 'departure'],
      ['Arrival Only', 'arrival'],
      ['Waypoints Only', 'waypoint'],
      ['Alternates Only', 'alternate'],
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
    for (const control of [
      screen.getByRole('button', { name: 'Overview controls' }),
      screen.getByRole('combobox', { name: 'Refresh cadence' }),
      screen.getByRole('combobox', { name: 'POI category' }),
      screen.getByRole('checkbox', { name: 'Weather radar' }),
      screen.getByRole('button', { name: 'Refresh overview' }),
    ]) {
      expect(control).toHaveClass('focus-visible:ring-2');
      expect(control).toHaveClass('min-h-11');
    }
    expect(screen.getByRole('checkbox', { name: 'Weather radar' })).toHaveClass(
      'min-w-11'
    );
    expect(
      screen.getByRole('checkbox', { name: 'Weather radar' }).tagName
    ).toBe('INPUT');
    expect(
      screen.getByRole('combobox', { name: 'Refresh cadence' }).tagName
    ).toBe('SELECT');

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

  it('consumes rejecting manual refresh clicks while controlled state recovers', async () => {
    const onManualRefresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('refresh failed'))
      .mockResolvedValueOnce(undefined);
    const { rerender, props } = renderControls(undefined, {
      onManualRefresh,
      manualRefreshPending: false,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));
    await Promise.resolve();
    rerender(
      <OverviewControls
        {...props}
        onManualRefresh={onManualRefresh}
        manualRefreshPending={false}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));
    await Promise.resolve();

    expect(onManualRefresh).toHaveBeenCalledTimes(2);
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

  it('stays controlled across rerender and remount with the same fixture', () => {
    const preferences = {
      ...createDefaultOverviewPreferences(),
      refreshCadence: 5 as const,
      radarEnabled: false,
      poiFilter: 'waypoint' as const,
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: false,
        clockSettingsExpanded: true,
      },
    };
    const first = renderControls(preferences);

    expect(
      screen.getByRole('combobox', { name: 'Refresh cadence' })
    ).toHaveValue('5');
    expect(screen.getByRole('combobox', { name: 'POI category' })).toHaveValue(
      'waypoint'
    );
    expect(screen.getByText('Radar off')).toBeVisible();
    first.unmount();
    renderControls(preferences);
    expect(
      screen.getByRole('combobox', { name: 'Refresh cadence' })
    ).toHaveValue('5');
    expect(screen.getByRole('combobox', { name: 'POI category' })).toHaveValue(
      'waypoint'
    );
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

    fireEvent.change(screen.getByLabelText('Clock time zone'), {
      target: { value: 'America/New_York' },
    });
    fireEvent.change(screen.getByLabelText('Clock label'), {
      target: { value: 'Duplicate canonical' },
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

    expect(screen.getByText('UTC first.')).toBeVisible();
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

  it('renders hostile labels literally and suppresses invalid relabel callbacks', () => {
    const preferences = {
      ...createDefaultOverviewPreferences(),
      clocks: [
        { id: 'utc', timeZone: 'UTC', label: 'UTC (Zulu)' },
        {
          id: 'tz:Europe/London',
          timeZone: 'Europe/London',
          label: '<img src=x onerror=1>',
        },
      ],
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: false,
        clockSettingsExpanded: true,
      },
    };
    const { props } = renderControls(preferences);

    expect(screen.getByDisplayValue('<img src=x onerror=1>')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
    fireEvent.change(screen.getByLabelText('Relabel <img src=x onerror=1>'), {
      target: { value: ' '.repeat(65) },
    });
    fireEvent.blur(screen.getByLabelText('Relabel <img src=x onerror=1>'));
    expect(props.onRelabelClock).not.toHaveBeenCalled();
  });

  it('syncs relabel drafts from controlled labels when not editing', () => {
    const preferences = {
      ...createDefaultOverviewPreferences(),
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: false,
        clockSettingsExpanded: true,
      },
    };
    const { rerender, props } = renderControls(preferences);

    rerender(
      <OverviewControls
        {...props}
        preferences={{
          ...preferences,
          clocks: preferences.clocks.map((clock) =>
            clock.id === 'tz:Asia/Tokyo'
              ? { ...clock, label: 'Tokyo External' }
              : clock
          ),
        }}
      />
    );
    expect(screen.getByLabelText('Relabel Tokyo External')).toHaveValue(
      'Tokyo External'
    );
  });

  it('preserves active relabel drafts until blur and then resumes syncing', () => {
    const preferences = {
      ...createDefaultOverviewPreferences(),
      disclosures: {
        controlsExpanded: true,
        additionalClocksExpanded: false,
        clockSettingsExpanded: true,
      },
    };
    const { rerender, props } = renderControls(preferences);
    const tokyo = screen.getByLabelText('Relabel Tokyo');

    fireEvent.focus(tokyo);
    fireEvent.change(tokyo, { target: { value: ' Tokyo Active ' } });
    const externallyUpdated = {
      ...preferences,
      clocks: preferences.clocks.map((clock) =>
        clock.id === 'tz:Asia/Tokyo'
          ? { ...clock, label: 'Tokyo External' }
          : clock
      ),
    };
    rerender(<OverviewControls {...props} preferences={externallyUpdated} />);
    expect(screen.getByLabelText('Relabel Tokyo External')).toHaveValue(
      ' Tokyo Active '
    );

    fireEvent.blur(screen.getByLabelText('Relabel Tokyo External'));
    expect(props.onRelabelClock).toHaveBeenCalledWith(
      'tz:Asia/Tokyo',
      'Tokyo Active'
    );

    const finalPreferences = {
      ...externallyUpdated,
      clocks: externallyUpdated.clocks.map((clock) =>
        clock.id === 'tz:Asia/Tokyo'
          ? { ...clock, label: 'Tokyo Final' }
          : clock
      ),
    };
    rerender(<OverviewControls {...props} preferences={finalPreferences} />);
    expect(screen.getByLabelText('Relabel Tokyo Final')).toHaveValue(
      'Tokyo Final'
    );
  });
});
