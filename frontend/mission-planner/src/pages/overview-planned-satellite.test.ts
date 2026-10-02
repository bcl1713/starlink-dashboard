import { describe, expect, it } from 'vitest';
import { derivePlannedSatelliteState } from './overview-planned-satellite';

describe('planned satellite selection', () => {
  it('uses the explicit selection without requiring telemetry or geometry', () => {
    expect(
      derivePlannedSatelliteState({ satellite_id: 'X-6' }, false, false)
    ).toEqual({ kind: 'selected', satelliteId: 'X-6' });
  });
  it('distinguishes an explicit empty selection from an unavailable response', () => {
    expect(
      derivePlannedSatelliteState({ satellite_id: null }, false, false)
    ).toEqual({ kind: 'none' });
    for (const value of [
      undefined,
      {},
      null,
      { satellite_id: '' },
      { satellite_id: ' ' },
      { satellite_id: 6 },
    ])
      expect(derivePlannedSatelliteState(value, false, false)).toEqual({
        kind: 'unavailable',
      });
  });
  it('does not expose cached selection as current after refresh failure', () => {
    expect(
      derivePlannedSatelliteState({ satellite_id: 'X-6' }, false, true)
    ).toEqual({ kind: 'unavailable' });
    expect(derivePlannedSatelliteState(undefined, true, false)).toEqual({
      kind: 'loading',
    });
  });
});
