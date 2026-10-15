import { expect, it } from 'vitest';
import {
  projectAdsbContacts,
  acceptAdsbBundle,
  emptyAdsbSnapshot,
} from './overview-adsb-state';
import {
  ADSB_NOW,
  adsbBundle,
  adsbContact,
  adsbSettings,
} from '@/test/adsb-fixtures';
it.each([
  [29999, 'current'],
  [30000, 'stale'],
  [30001, 'stale'],
  [119999, 'stale'],
  [120000, undefined],
  [120001, undefined],
] as const)('uses exact observation-age boundary %s', (age, state) => {
  expect(
    projectAdsbContacts([adsbContact()], adsbSettings(), ADSB_NOW + age)[0]
      ?.freshness
  ).toBe(state);
});
it('applies exclusion, civilian inclusion, mode and callsign OR in order', () => {
  const contacts = [
    adsbContact({ military: false }),
    adsbContact({ hex: '000002', callsign: ' reach9 ' }),
    adsbContact({ hex: '000003', callsign: 'NO' }),
  ];
  expect(
    projectAdsbContacts(
      contacts,
      adsbSettings({
        include_hexes: ['00AB12'],
        callsign_substrings: ['RCH', 'REACH'],
      }),
      ADSB_NOW
    ).map((c) => c.hex)
  ).toEqual(['000002', '00AB12']);
  expect(
    projectAdsbContacts(
      contacts,
      adsbSettings({
        include_hexes: ['00AB12'],
        exclude_hexes: ['00AB12'],
        mode: 'included_only',
      }),
      ADSB_NOW
    )
  ).toEqual([]);
  expect(
    projectAdsbContacts(contacts, adsbSettings({ enabled: false }), ADSB_NOW)
  ).toEqual([]);
});
it('deduplicates newest observation and applies honest label fallbacks', () => {
  const old = adsbContact({
    position_observed_at_ms: ADSB_NOW - 10000,
    callsign: 'OLD',
  });
  const latest = adsbContact({ callsign: null });
  expect(
    projectAdsbContacts(
      [old, latest],
      adsbSettings({ include_hexes: ['00AB12'] }),
      ADSB_NOW
    )[0]
  ).toMatchObject({ label: 'N123', included: true });
  expect(
    projectAdsbContacts(
      [adsbContact({ callsign: null, registration: null })],
      adsbSettings(),
      ADSB_NOW
    )[0].label
  ).toBe('00AB12');
});
it('rejects mismatched revision, regressing bundles and older observations', () => {
  const settings = adsbSettings();
  const state = acceptAdsbBundle(emptyAdsbSnapshot(), settings, adsbBundle());
  expect(
    acceptAdsbBundle(
      state,
      adsbSettings({ revision: 2, exclude_hexes: ['00AB12'] }),
      adsbBundle()
    ).contacts
  ).toEqual([]);
  expect(
    acceptAdsbBundle(
      state,
      settings,
      adsbBundle({ generated_at_ms: ADSB_NOW - 1 })
    )
  ).toEqual(state);
  const old = adsbBundle({
    generated_at_ms: ADSB_NOW + 1000,
    contacts: [adsbContact({ position_observed_at_ms: ADSB_NOW - 1 })],
  });
  expect(
    acceptAdsbBundle(state, settings, old).contacts[0].position_observed_at_ms
  ).toBe(ADSB_NOW);
  expect(
    acceptAdsbBundle(state, settings, adsbBundle({ settings_revision: 2 }))
  ).toEqual(state);
});
it('disable clears snapshots so re-enable cannot reuse the old bundle', () => {
  const state = acceptAdsbBundle(
    emptyAdsbSnapshot(),
    adsbSettings(),
    adsbBundle()
  );
  const off = acceptAdsbBundle(
    state,
    adsbSettings({ enabled: false, revision: 2 }),
    adsbBundle()
  );
  expect(off.contacts).toEqual([]);
  expect(
    acceptAdsbBundle(off, adsbSettings({ revision: 3 }), adsbBundle()).contacts
  ).toEqual([]);
});
