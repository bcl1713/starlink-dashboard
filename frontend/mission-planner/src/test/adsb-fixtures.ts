import type {
  AdsbContact,
  AdsbSettings,
  AdsbTrafficBundle,
} from '@/services/overview-adsb';
export const ADSB_NOW = 1791028800000;
export function adsbSettings(
  changes: Partial<AdsbSettings> = {}
): AdsbSettings {
  return {
    enabled: true,
    mode: 'military_and_included',
    include_hexes: [],
    exclude_hexes: [],
    callsign_substrings: [],
    revision: 1,
    ...changes,
  };
}
export function adsbContact(changes: Partial<AdsbContact> = {}): AdsbContact {
  return {
    hex: '00AB12',
    callsign: 'RCH123',
    registration: 'N123',
    aircraft_type: 'C17',
    military: true,
    latitude: 40,
    longitude: -75,
    altitude: { value: 30000, unit: 'ft', source: 'barometric' },
    ground_speed_knots: 450,
    track_degrees: 90,
    position_observed_at_ms: ADSB_NOW,
    acquired_at_ms: ADSB_NOW,
    ...changes,
  };
}
export function adsbBundle(
  changes: Partial<AdsbTrafficBundle> = {}
): AdsbTrafficBundle {
  return {
    settings_revision: 1,
    generated_at_ms: ADSB_NOW,
    contacts: [adsbContact()],
    sources: [],
    ...changes,
  };
}
