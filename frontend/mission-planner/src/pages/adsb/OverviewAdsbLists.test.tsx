/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewAdsbLists } from './OverviewAdsbLists';
import { adsbSettings, adsbContact } from '@/test/adsb-fixtures';
afterEach(cleanup);
it('normalizes exact hex entries and preserves leading zeroes in partial updates', () => {
  const save = vi.fn();
  render(
    <OverviewAdsbLists
      settings={adsbSettings()}
      disabled={false}
      onSave={save}
    />
  );
  fireEvent.change(screen.getByLabelText('Included ICAO hexes'), {
    target: { value: ' 00ab12,000002\n00AB12' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Save included aircraft' })
  );
  expect(save).toHaveBeenCalledWith({ include_hexes: ['00AB12', '000002'] });
});
it.each(['12345', '1234567', '~AB1234', 'ZZ1234'])(
  'rejects invalid hex %s visibly',
  (value) => {
    const save = vi.fn();
    render(
      <OverviewAdsbLists
        settings={adsbSettings()}
        disabled={false}
        onSave={save}
      />
    );
    fireEvent.change(screen.getByLabelText('Included ICAO hexes'), {
      target: { value },
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Save included aircraft' })
    );
    expect(screen.getByRole('alert')).toHaveTextContent(/six hexadecimal/);
    expect(save).not.toHaveBeenCalled();
  }
);
it('keeps unavailable and conflicting saved entries separately editable', () => {
  const save = vi.fn();
  render(
    <OverviewAdsbLists
      settings={adsbSettings({
        enabled: false,
        include_hexes: ['00AB12'],
        exclude_hexes: ['00AB12'],
      })}
      disabled={false}
      onSave={save}
    />
  );
  expect(
    within(
      screen.getByRole('region', { name: 'Saved included aircraft' })
    ).getByRole('button', { name: 'Remove included 00AB12' })
  ).toBeVisible();
  expect(
    within(
      screen.getByRole('region', { name: 'Saved excluded aircraft' })
    ).getByRole('button', { name: 'Remove excluded 00AB12' })
  ).toBeVisible();
  expect(screen.getByText(/Exclusion always wins/)).toBeVisible();
  fireEvent.click(
    screen.getByRole('button', { name: 'Remove excluded 00AB12' })
  );
  expect(save).toHaveBeenCalledWith({ exclude_hexes: [] });
});
it('callsign filters trim and deduplicate, combine with OR', () => {
  const save = vi.fn();
  render(
    <OverviewAdsbLists
      settings={adsbSettings()}
      disabled={false}
      onSave={save}
    />
  );
  fireEvent.change(
    screen.getByLabelText('Background military callsign substrings'),
    { target: { value: ' rch,\n reach , RCH,' } }
  );
  fireEvent.click(screen.getByRole('button', { name: 'Save callsign filter' }));
  expect(save).toHaveBeenCalledWith({ callsign_substrings: ['RCH', 'REACH'] });
  expect(screen.getByText(/any substring/)).toBeVisible();
});
it('remote confirmations do not wipe unrelated unsaved text', () => {
  const settings = adsbSettings();
  const props = { settings, disabled: false, onSave: vi.fn() };
  const view = render(<OverviewAdsbLists {...props} />);
  fireEvent.change(screen.getByLabelText('Included ICAO hexes'), {
    target: { value: '00ab12' },
  });
  view.rerender(
    <OverviewAdsbLists
      {...props}
      settings={adsbSettings({ revision: 2, exclude_hexes: ['000002'] })}
    />
  );
  expect(screen.getByLabelText('Included ICAO hexes')).toHaveValue('00ab12');
  expect(screen.getByLabelText('Excluded ICAO hexes')).toHaveValue('000002');
});
it('pending saves disable edits', () => {
  render(
    <OverviewAdsbLists settings={adsbSettings()} disabled onSave={vi.fn()} />
  );
  expect(screen.getByLabelText('Included ICAO hexes')).toBeDisabled();
});

it('adds current contact context to saved hexes while keeping edits and removals hex-only', () => {
  const save = vi.fn();
  const view = render(
    <OverviewAdsbLists
      settings={adsbSettings({
        include_hexes: ['00AB12', '000002'],
        exclude_hexes: ['00AB12'],
      })}
      contacts={[adsbContact()]}
      disabled={false}
      onSave={save}
    />
  );
  expect(screen.getAllByText('00AB12 · RCH123 · N123 · C17')).toHaveLength(2);
  expect(screen.getByText('000002')).toBeVisible();
  expect(screen.getByLabelText('Included ICAO hexes')).toHaveValue(
    '00AB12\n000002'
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Remove included 00AB12' })
  );
  expect(save).toHaveBeenCalledWith({ include_hexes: ['000002'] });
  view.rerender(
    <OverviewAdsbLists
      settings={adsbSettings({ include_hexes: ['00AB12', '000002'] })}
      contacts={[]}
      disabled={false}
      onSave={save}
    />
  );
  expect(screen.getByText('00AB12')).toBeVisible();
  expect(screen.queryByText(/RCH123/)).toBeNull();
});
it('omits missing identity fields from saved context', () => {
  render(
    <OverviewAdsbLists
      settings={adsbSettings({ exclude_hexes: ['00AB12'] })}
      contacts={[
        adsbContact({
          callsign: null,
          registration: '  ',
          aircraft_type: 'C17',
        }),
      ]}
      disabled={false}
      onSave={vi.fn()}
    />
  );
  expect(screen.getByText('00AB12 · C17')).toBeVisible();
});
