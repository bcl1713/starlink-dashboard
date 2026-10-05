/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { OverviewAdsbSourceStatus } from './OverviewAdsbSourceStatus';
import { OverviewAdsbSettingsCard } from './OverviewAdsbSettingsCard';
import type { useOverviewAdsbLayer } from '@/hooks/useOverviewAdsbLayer';
import { adsbContact, adsbSettings, ADSB_NOW } from '@/test/adsb-fixtures';
import { projectAdsbCatalog } from './overview-adsb-state';
let state: ReturnType<typeof useOverviewAdsbLayer> & {
  contextContacts: ReturnType<typeof adsbContact>[];
};
const save = vi.fn();
let pending = false,
  saveError = false;
vi.mock('@/hooks/useOverviewAdsbLayer', () => ({
  useOverviewAdsbLayer: () => state,
}));
vi.mock('@/hooks/useConfigurationAdsbLayer', () => ({
  useConfigurationAdsbLayer: () => ({
    ...state,
    contacts: projectAdsbCatalog(
      state.contextContacts,
      state.settings ?? adsbSettings({ enabled: false }),
      ADSB_NOW
    ),
    sourceErrors: [],
  }),
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
    contextContacts: [],
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
it('exclusion marks the catalog row only after confirmation while keeping the saved list', () => {
  state.settings = adsbSettings();
  state.contextContacts = [adsbContact()];
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
  expect(screen.getByRole('row', { name: /00AB12/ })).toHaveTextContent(
    'Excluded'
  );
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
  render(
    <>
      <OverviewAdsbSettingsCard />
      <OverviewAdsbSourceStatus />
    </>
  );
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

it('uses available identity context for an excluded aircraft and keeps it manageable', () => {
  state.settings = adsbSettings({ exclude_hexes: ['00AB12'] });
  state.contextContacts = [adsbContact()];
  render(<OverviewAdsbSettingsCard />);
  expect(
    screen.getByRole('region', { name: 'Saved excluded aircraft' })
  ).toHaveTextContent('00AB12 · RCH123 · N123 · C17');
  expect(screen.getByRole('row', { name: /00AB12/ })).toHaveTextContent(
    'Excluded'
  );
});

it('toggles each saved list independently using confirmed membership and exclusion precedence', () => {
  state.settings = adsbSettings({
    mode: 'included_only',
    include_hexes: ['00AB12'],
    exclude_hexes: ['00AB12'],
  });
  state.contextContacts = [adsbContact()];
  const view = render(<OverviewAdsbSettingsCard />);
  const include = () => screen.getByRole('button', { name: 'Include 00AB12' });
  const exclude = () => screen.getByRole('button', { name: 'Exclude 00AB12' });
  expect(include()).toHaveAttribute('aria-pressed', 'true');
  expect(exclude()).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('row', { name: /00AB12/ })).toHaveTextContent(
    'Excluded'
  );
  fireEvent.click(include());
  expect(save).toHaveBeenLastCalledWith({ include_hexes: [] });
  expect(include()).toHaveAttribute('aria-pressed', 'true');
  state.settings = adsbSettings({
    mode: 'included_only',
    exclude_hexes: ['00AB12'],
    revision: 2,
  });
  view.rerender(<OverviewAdsbSettingsCard />);
  expect(include()).toHaveAttribute('aria-pressed', 'false');
  expect(exclude()).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(exclude());
  expect(save).toHaveBeenLastCalledWith({ exclude_hexes: [] });
  state.settings = adsbSettings({ mode: 'included_only', revision: 3 });
  view.rerender(<OverviewAdsbSettingsCard />);
  expect(exclude()).toHaveAttribute('aria-pressed', 'false');
  expect(screen.getByRole('row', { name: /00AB12/ })).toHaveTextContent(
    'Not selected'
  );
  fireEvent.click(include());
  expect(save).toHaveBeenLastCalledWith({ include_hexes: ['00AB12'] });
});
