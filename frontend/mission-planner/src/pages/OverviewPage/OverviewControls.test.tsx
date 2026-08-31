import { fireEvent, render, screen, within } from '@testing-library/react';
import type React from 'react';
import { describe, expect, it, vi } from 'vitest';
import {
  createDefaultOverviewPreferences,
  type OverviewPreferences,
} from './preferences';
import { OverviewControls } from './OverviewControls';

function expandedPreferences(): OverviewPreferences {
  return {
    ...createDefaultOverviewPreferences(),
    disclosures: {
      controlsExpanded: true,
      additionalClocksExpanded: false,
      clockSettingsExpanded: false,
    },
  };
}

function renderControls(
  preferences = expandedPreferences(),
  overrides: Partial<React.ComponentProps<typeof OverviewControls>> = {}
) {
  const props: React.ComponentProps<typeof OverviewControls> = {
    preferences,
    manualRefreshPending: false,
    onRefreshCadenceChange: vi.fn(),
    onManualRefresh: vi.fn(),
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
  it('renders one accessible control set without radar ownership', () => {
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
      screen.queryByRole('checkbox', { name: 'Weather radar' })
    ).toBeNull();

    fireEvent.change(
      screen.getByRole('combobox', { name: 'Refresh cadence' }),
      { target: { value: '10' } }
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'POI category' }), {
      target: { value: 'alternate' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));

    expect(props.onRefreshCadenceChange).toHaveBeenCalledWith(10);
    expect(props.onPOIFilterChange).toHaveBeenCalledWith('alternate');
    expect(props.onManualRefresh).toHaveBeenCalledTimes(1);
  });

  it('uses controlled disclosure and unavailable manual refresh state', () => {
    const { rerender, props } = renderControls(undefined, {
      manualRefreshPending: true,
    });
    const manual = screen.getByRole('button', { name: 'Refresh overview' });

    expect(manual).toHaveAttribute('aria-disabled', 'true');
    expect(manual).not.toBeDisabled();
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
      screen.getByRole('button', { name: 'Clock settings' })
    ).toHaveAttribute('aria-expanded', 'true');
  });

  it('retains refresh focus while duplicate activation is unavailable', () => {
    const { rerender, props } = renderControls();
    const manual = screen.getByRole('button', { name: 'Refresh overview' });
    manual.focus();
    fireEvent.click(manual);
    manual.blur();

    rerender(<OverviewControls {...props} manualRefreshPending />);

    expect(manual).toHaveFocus();
    expect(manual).toHaveAttribute('aria-disabled', 'true');
    expect(manual).not.toBeDisabled();
    fireEvent.click(manual);
    expect(props.onManualRefresh).toHaveBeenCalledTimes(1);
  });

  it('consumes rejecting manual refresh clicks while controlled state recovers', async () => {
    const onManualRefresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('refresh failed'))
      .mockResolvedValueOnce(undefined);
    const { rerender, props } = renderControls(undefined, {
      onManualRefresh,
    });

    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));
    await Promise.resolve();
    rerender(<OverviewControls {...props} onManualRefresh={onManualRefresh} />);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh overview' }));
    await Promise.resolve();

    expect(onManualRefresh).toHaveBeenCalledTimes(2);
  });
});
