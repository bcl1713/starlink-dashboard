import { expect, it } from 'vitest';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
import { projectAdsbCatalog } from './overview-adsb-state';
it('keeps military catalog independent from Overview selection and marks exclusions first', () => {
  const settings = adsbSettings({
    mode: 'included_only',
    include_hexes: ['000001', '000002'],
    exclude_hexes: ['000002'],
    callsign_substrings: ['NONE'],
  });
  const contacts = [
    adsbContact({ hex: '000001' }),
    adsbContact({ hex: '000002' }),
    adsbContact({ hex: '000003' }),
    adsbContact({ hex: '000004', position_observed_at_ms: ADSB_NOW - 120000 }),
  ];
  const views = projectAdsbCatalog(contacts, settings, ADSB_NOW);
  expect(views.map((c) => [c.hex, c.selection])).toEqual([
    ['000001', 'included'],
    ['000002', 'excluded'],
    ['000003', 'not_selected'],
  ]);
  expect(
    projectAdsbCatalog(contacts, { ...settings, enabled: false }, ADSB_NOW)
  ).toEqual([]);
});

it('uses the newest current identity and rejects future or expired samples', () => {
  const contacts = [
    adsbContact({ callsign: 'OLD', position_observed_at_ms: ADSB_NOW - 10000 }),
    adsbContact({ callsign: 'NEW' }),
    adsbContact({ hex: '000001', position_observed_at_ms: ADSB_NOW - 120000 }),
    adsbContact({
      hex: '000002',
      acquired_at_ms: ADSB_NOW + 1000,
      position_observed_at_ms: ADSB_NOW + 1000,
    }),
  ];
  expect(
    projectAdsbCatalog(contacts, adsbSettings(), ADSB_NOW).map(
      (c) => c.callsign
    )
  ).toEqual(['NEW']);
});
