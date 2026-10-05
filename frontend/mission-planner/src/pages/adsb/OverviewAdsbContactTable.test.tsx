/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewAdsbContactTable } from './OverviewAdsbContactTable';
import { projectAdsbContacts } from './overview-adsb-state';
import { ADSB_NOW, adsbSettings, adsbContact } from '@/test/adsb-fixtures';
afterEach(cleanup);
it('lists globally eligible contacts including the rear hemisphere, with stable hex actions', () => {
  const contacts = projectAdsbContacts(
    [
      adsbContact(),
      adsbContact({
        hex: '000002',
        latitude: -40,
        longitude: 105,
        position_observed_at_ms: ADSB_NOW - 40000,
      }),
    ],
    adsbSettings(),
    ADSB_NOW
  );
  const include = vi.fn(),
    exclude = vi.fn();
  render(
    <OverviewAdsbContactTable
      contacts={contacts}
      disabled={false}
      onInclude={include}
      onExclude={exclude}
    />
  );
  expect(screen.getAllByRole('row')).toHaveLength(3);
  expect(screen.getByText(/Stale/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Include 00AB12' }));
  expect(include).toHaveBeenCalledWith('00AB12');
  fireEvent.click(screen.getByRole('button', { name: 'Exclude 000002' }));
  expect(exclude).toHaveBeenCalledWith('000002');
});
it('keeps long and fallback identities and disables pending actions', () => {
  const contacts = projectAdsbContacts(
    [
      adsbContact({ callsign: 'LONG IDENTITY THAT MUST NOT HIDE ACTIONS' }),
      adsbContact({ hex: '000002', callsign: null, registration: null }),
    ],
    adsbSettings(),
    ADSB_NOW
  );
  render(
    <OverviewAdsbContactTable
      contacts={contacts}
      disabled
      onInclude={vi.fn()}
      onExclude={vi.fn()}
    />
  );
  expect(
    screen.getByText('LONG IDENTITY THAT MUST NOT HIDE ACTIONS')
  ).toBeVisible();
  expect(screen.getByRole('button', { name: 'Include 000002' })).toBeDisabled();
});
it('has an accessible empty state', () => {
  render(
    <OverviewAdsbContactTable
      contacts={[]}
      disabled={false}
      onInclude={vi.fn()}
      onExclude={vi.fn()}
    />
  );
  expect(screen.getByText(/No active aircraft/)).toBeVisible();
});
