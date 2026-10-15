/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import { createRef } from 'react';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewAdsbDetails } from './OverviewAdsbDetails';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
import { projectAdsbContacts } from './overview-adsb-state';
afterEach(() => {
  cleanup();
  document.body.replaceChildren();
});
it('shows honest optional values, units, track, staleness and no editing in the stage portal', async () => {
  const stage = document.createElement('div');
  document.body.append(stage);
  const contact = projectAdsbContacts(
    [adsbContact({ position_observed_at_ms: ADSB_NOW - 40000 })],
    adsbSettings(),
    ADSB_NOW
  )[0];
  render(
    <OverviewAdsbDetails
      contact={contact}
      onClose={vi.fn()}
      returnFocusRef={createRef()}
      portalContainer={stage}
    />
  );
  const dialog = screen.getByRole('dialog');
  expect(stage.contains(dialog)).toBe(true);
  expect(dialog).toHaveTextContent('30000 ft (barometric)');
  expect(dialog).toHaveTextContent('450 knots');
  expect(dialog).toHaveTextContent('Track');
  expect(dialog).toHaveTextContent('Stale');
  expect(dialog).toHaveTextContent('00AB12');
  expect(screen.queryByRole('button', { name: 'Include' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Exclude' })).toBeNull();
});
it('supports Escape, close and focus restoration, showing unavailable fields', async () => {
  const stage = document.createElement('div');
  const trigger = document.createElement('button');
  trigger.textContent = 'Map control';
  document.body.append(trigger, stage);
  trigger.focus();
  const focus = createRef<HTMLElement>();
  focus.current = trigger;
  const close = vi.fn();
  const contact = projectAdsbContacts(
    [
      adsbContact({
        callsign: null,
        registration: null,
        aircraft_type: null,
        military: null,
        altitude: null,
        ground_speed_knots: null,
        track_degrees: null,
      }),
    ],
    adsbSettings({ include_hexes: ['00AB12'] }),
    ADSB_NOW
  )[0];
  const view = render(
    <OverviewAdsbDetails
      contact={contact}
      onClose={close}
      returnFocusRef={focus}
      portalContainer={stage}
    />
  );
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(6);
  expect(screen.getByRole('dialog')).toContainElement(
    document.activeElement as HTMLElement
  );
  fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
  expect(close).toHaveBeenCalled();
  view.rerender(
    <OverviewAdsbDetails
      contact={null}
      onClose={close}
      returnFocusRef={focus}
      portalContainer={stage}
    />
  );
  await waitFor(() => expect(trigger).toHaveFocus());
});
