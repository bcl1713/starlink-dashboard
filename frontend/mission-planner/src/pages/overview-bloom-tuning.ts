import type { BloomSettings } from '../experiments/bloom/contracts';
import type { BloomEmission } from './overview-bloom-mode';

// Owner-selected live Overview values from the October 28 tuning session.
export const OVERVIEW_BLOOM_SETTINGS: BloomSettings = {
  strength: 0.35,
  threshold: 0.8,
  radius: 1,
  maxDimension: 3840,
  exposure: 1,
  view: 'final',
};
export const OVERVIEW_BLOOM_EMISSIONS: BloomEmission = {
  cities: 17,
  cityColor: '#ffbe6f',
  lines: 3.9,
  particles: 0.2,
  pois: 40,
  aircraft: 2.8,
};
