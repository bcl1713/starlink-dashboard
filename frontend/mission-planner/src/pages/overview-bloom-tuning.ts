import type { BloomSettings } from '../experiments/bloom/contracts';
import type { BloomEmission } from './overview-bloom-mode';

// Owner-selected live Overview values from the October 28 tuning session.
export const OVERVIEW_BLOOM_SETTINGS: BloomSettings = {
  strength: 0.15,
  threshold: 0.3,
  radius: 0,
  maxDimension: 3840,
  exposure: 1,
  view: 'final',
};
export const OVERVIEW_BLOOM_EMISSIONS: BloomEmission = {
  cities: 6,
  cityColor: '#ffbe6f',
  lines: 1.7,
  particles: 0.6,
  pois: 25,
  aircraft: 4.3,
};

export const OVERVIEW_BLOOM_AMBIENT_INTENSITY = 0.1;

export const OVERVIEW_BLOOM_ATMOSPHERE_INTENSITY = 0;
