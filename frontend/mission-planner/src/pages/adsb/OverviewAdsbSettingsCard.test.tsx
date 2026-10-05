/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { OverviewAdsbSettingsCard } from './OverviewAdsbSettingsCard';
import type { useOverviewAdsbLayer } from '@/hooks/useOverviewAdsbLayer';
import { adsbContact, adsbSettings, ADSB_NOW } from '@/test/adsb-fixtures';
import { projectAdsbContacts } from './overview-adsb-state';
let state: ReturnType<typeof useOverviewAdsbLayer>;
const save = vi.fn();
let pending = false,
  saveError = false;
vi.mock('@/hooks/useOverviewAdsbLayer', () => ({
  useOverviewAdsbLayer: () => state,
}));
vi.mock('@/hooks/api/useUpdateOverviewAdsbSettings', () => ({
  useUpdateOverviewAdsbSettings: () => ({
    mutate: save,
    isPending: pending,
    isError: saveError,
    isSuccess: false,
  }),
}));
beforeEach(() => {
  save.mockReset();
  pending = saveError = false;
  state = {
    settings: adsbSettings({ enabled: false }),
    contacts: [],
    sources: [],
    settingsError: false,
    trafficError: false,
  };
});
afterEach(cleanup);
it('defaults off and uses confirmed enable/mode controls with exact mode names', () => {
  render(<OverviewAdsbSettingsCard />);
  expect(
    screen.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).not.toBeChecked();
  fireEvent.click(screen.getByRole('switch', { name: 'ADS-B aircraft layer' }));
  expect(save).toHaveBeenCalledWith({ enabled: true });
  expect(
    screen.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).not.toBeChecked();
  fireEvent.change(screen.getByLabelText('ADS-B mode'), {
    target: { value: 'included_only' },
  });
  expect(save).toHaveBeenCalledWith({ mode: 'included_only' });
  expect(
    screen.getByRole('option', { name: 'Military + included' })
  ).toBeInTheDocument();
  expect(
    screen.getByRole('option', { name: 'Included only' })
  ).toBeInTheDocument();
});
it('exclusion removes the active row only after confirmation while keeping the saved list', () => {
  state.settings = adsbSettings();
  state.contacts = projectAdsbContacts(
    [adsbContact()],
    state.settings,
    ADSB_NOW
  );
  const view = render(<OverviewAdsbSettingsCard />);
  fireEvent.click(screen.getByRole('button', { name: 'Exclude 00AB12' }));
  expect(save).toHaveBeenCalledWith({ exclude_hexes: ['00AB12'] });
  expect(screen.getByRole('row', { name: /00AB12/ })).toBeInTheDocument();
  state = {
    ...state,
    settings: adsbSettings({ revision: 2, exclude_hexes: ['00AB12'] }),
    contacts: [],
  };
  view.rerender(<OverviewAdsbSettingsCard />);
  expect(screen.queryByRole('row', { name: /00AB12/ })).toBeNull();
  expect(
    screen.getByRole('region', { name: 'Saved excluded aircraft' })
  ).toHaveTextContent('00AB12');
});
it('shows loading, settings/save errors and pending feedback without losing confirmed values', () => {
  state.settings = undefined;
  const view = render(<OverviewAdsbSettingsCard />);
  expect(screen.getByRole('status')).toHaveTextContent(/Loading ADS-B/);
  state = { ...state, settings: adsbSettings(), settingsError: true };
  saveError = true;
  pending = true;
  view.rerender(<OverviewAdsbSettingsCard />);
  expect(screen.getByText('ADS-B settings unavailable')).toBeVisible();
  expect(screen.getByText(/Unable to save ADS-B/)).toBeVisible();
  expect(
    screen.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).toBeChecked();
  expect(
    screen.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).toBeDisabled();
});
it('shows independent source status and provider attribution', () => {
  state.sources = [
    {
      key: 'military',
      last_success_at_ms: ADSB_NOW,
      error: 'Provider acquisition failed',
      retry_at_ms: ADSB_NOW + 15000,
    },
  ];
  render(<OverviewAdsbSettingsCard />);
  expect(screen.getByText(/Provider acquisition failed/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'adsb.lol' })).toHaveAttribute(
    'href',
    'https://www.adsb.lol/'
  );
  expect(screen.getByRole('link', { name: 'ODbL license' })).toHaveAttribute(
    'href',
    'https://opendatacommons.org/licenses/odbl/1-0/'
  );
});
