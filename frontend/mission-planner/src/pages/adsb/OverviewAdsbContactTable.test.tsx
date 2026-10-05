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

it('exposes separate identity, flight and freshness columns without hiding zero values', () => {
  const contacts = projectAdsbContacts(
    [
      adsbContact({
        altitude: { value: 0, unit: 'ft', source: 'geometric' },
        ground_speed_knots: 0,
      }),
      adsbContact({
        hex: '000002',
        callsign: null,
        registration: null,
        aircraft_type: null,
        altitude: null,
        ground_speed_knots: null,
        position_observed_at_ms: ADSB_NOW - 40000,
      }),
    ],
    adsbSettings({ include_hexes: ['00AB12'] }),
    ADSB_NOW
  );
  render(
    <OverviewAdsbContactTable
      contacts={contacts}
      disabled={false}
      onInclude={vi.fn()}
      onExclude={vi.fn()}
    />
  );
  for (const name of [
    'Callsign',
    'Registration',
    'Aircraft type',
    'ICAO hex',
    'Altitude',
    'Ground speed',
    'Position age',
    'Selection',
    'Actions',
  ])
    expect(screen.getByRole('columnheader', { name })).toBeVisible();
  const row = within(screen.getByRole('row', { name: /00AB12/ }));
  for (const value of ['RCH123', 'N123', 'C17', '0 ft', '0 kt', 'Included'])
    expect(row.getByText(value)).toBeVisible();
  expect(row.getByText('0 ft')).toHaveAttribute('title', 'Geometric altitude');
  expect(row.getByRole('button', { name: 'Include 00AB12' })).toBeEnabled();
  expect(row.getByRole('button', { name: 'Include 00AB12' })).toHaveAttribute(
    'aria-pressed',
    'true'
  );
  expect(row.getByRole('button', { name: 'Exclude 00AB12' })).toHaveAttribute(
    'aria-pressed',
    'false'
  );
  const unknown = within(screen.getByRole('row', { name: /000002/ }));
  expect(unknown.getAllByText('—')).toHaveLength(5);
  expect(unknown.getByText(/Stale/)).toBeVisible();
  expect(unknown.getByText(/40s/)).toBeVisible();
});

it('searches all contact fields case-insensitively without changing selection', () => {
  const contacts = projectAdsbContacts(
    [
      adsbContact({ hex: '000001', aircraft_type: 'C560' }),
      adsbContact({ hex: '3C5602', aircraft_type: 'B738', callsign: 'OTHER' }),
      adsbContact({
        hex: '000003',
        registration: 'D-TEST',
        callsign: 'VIP001',
        track_degrees: 123,
      }),
    ],
    adsbSettings(),
    ADSB_NOW
  );
  render(
    <OverviewAdsbContactTable
      contacts={contacts}
      disabled={false}
      onInclude={vi.fn()}
      onExclude={vi.fn()}
    />
  );
  const search = screen.getByRole('searchbox', { name: 'Search aircraft' });
  fireEvent.change(search, { target: { value: 'c560' } });
  expect(screen.getAllByRole('row')).toHaveLength(3);
  expect(screen.getByRole('row', { name: /000001/ })).toBeVisible();
  expect(screen.getByRole('row', { name: /3C5602/ })).toBeVisible();
  expect(screen.queryByRole('row', { name: /000003/ })).toBeNull();
  for (const value of ['d-test', 'vip001', '123']) {
    fireEvent.change(search, { target: { value } });
    expect(screen.getByRole('row', { name: /000003/ })).toBeVisible();
  }
  fireEvent.change(search, { target: { value: 'no such aircraft' } });
  expect(screen.getByText(/No aircraft match/)).toBeVisible();
  fireEvent.change(search, { target: { value: '' } });
  expect(screen.getAllByRole('row')).toHaveLength(4);
  expect(screen.getByRole('region', { name: 'Aircraft list' })).toHaveAttribute(
    'tabindex',
    '0'
  );
});
