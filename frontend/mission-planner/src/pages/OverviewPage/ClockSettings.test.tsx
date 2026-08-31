import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { addOverviewClock, createDefaultOverviewPreferences } from './preferences';
import { ClockSettings } from './ClockSettings';

function renderSettings(
  clocks = createDefaultOverviewPreferences().clocks,
  overrides: Partial<React.ComponentProps<typeof ClockSettings>> = {}
) {
  const props: React.ComponentProps<typeof ClockSettings> = {
    clocks,
    expanded: true,
    onExpandedChange: vi.fn(),
    onAddClock: vi.fn(),
    onRelabelClock: vi.fn(),
    onMoveClock: vi.fn(),
    onRemoveClock: vi.fn(),
    ...overrides,
  };
  const view = render(<ClockSettings {...props} />);
  return { ...view, props };
}

describe('ClockSettings', () => {
  it('describes validation without creating a status live region', () => {
    const { props } = renderSettings();

    fireEvent.change(screen.getByLabelText('Clock time zone'), {
      target: { value: 'Etc/UTC' },
    });
    fireEvent.change(screen.getByLabelText('Clock label'), {
      target: { value: 'Zulu' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add clock' }));

    const validation = screen.getByText('Clock already exists.');
    expect(validation).toBeVisible();
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.getByLabelText('Clock time zone')).toHaveAttribute(
      'aria-describedby',
      validation.id
    );
    expect(screen.getByLabelText('Clock label')).toHaveAttribute(
      'aria-describedby',
      validation.id
    );
    expect(screen.getByRole('button', { name: 'Add clock' })).toHaveAttribute(
      'aria-describedby',
      validation.id
    );
    expect(props.onAddClock).not.toHaveBeenCalled();
  });

  it('adds valid clocks and enforces UTC edit restrictions', () => {
    const { props } = renderSettings();

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
    expect(screen.getByText('UTC first.')).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Remove UTC (Zulu)' })
    ).toBeNull();
  });

  it('supports bounded relabel, move, remove, and external label syncing', () => {
    let preferences = createDefaultOverviewPreferences();
    preferences = addOverviewClock(preferences, {
      timeZone: 'Europe/London',
      label: '<img src=x onerror=1>',
    });
    const { props, rerender } = renderSettings(preferences.clocks);

    expect(screen.getByDisplayValue('<img src=x onerror=1>')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
    const hostile = screen.getByLabelText('Relabel <img src=x onerror=1>');
    fireEvent.change(hostile, { target: { value: ' '.repeat(65) } });
    fireEvent.blur(hostile);
    expect(props.onRelabelClock).not.toHaveBeenCalled();

    const tokyo = screen.getByLabelText('Relabel Tokyo');
    fireEvent.focus(tokyo);
    fireEvent.change(tokyo, { target: { value: ' Tokyo Prime ' } });
    fireEvent.blur(tokyo);
    fireEvent.click(screen.getByRole('button', { name: 'Move Tokyo down' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove Tokyo' }));

    expect(props.onRelabelClock).toHaveBeenCalledWith(
      'tz:Asia/Tokyo',
      'Tokyo Prime'
    );
    expect(props.onMoveClock).toHaveBeenCalledWith('tz:Asia/Tokyo', 'down');
    expect(props.onRemoveClock).toHaveBeenCalledWith('tz:Asia/Tokyo');

    rerender(
      <ClockSettings
        {...props}
        clocks={preferences.clocks.map((clock) =>
          clock.id === 'tz:Asia/Tokyo'
            ? { ...clock, label: 'Tokyo External' }
            : clock
        )}
      />
    );
    expect(screen.getByLabelText('Relabel Tokyo External')).toHaveValue(
      'Tokyo External'
    );
  });
});
