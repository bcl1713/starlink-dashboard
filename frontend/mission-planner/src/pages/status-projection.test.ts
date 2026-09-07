import { describe, expect, it } from 'vitest';
import { projectAircraftPosition } from './status-projection.ts';

describe('status-projection', () => {
  it('projects valid status latitude and longitude as an aircraft position', () => {
    const result = projectAircraftPosition({
      position: {
        latitude: 51.5074,
        longitude: -0.1278,
      },
    });

    expect(result).toEqual({
      latitude: 51.5074,
      longitude: -0.1278,
    });
  });

  it('returns null when status has no position', () => {
    expect(projectAircraftPosition({})).toBeNull();
  });

  it('returns null when latitude is outside the geographic range', () => {
    expect(
      projectAircraftPosition({
        position: {
          latitude: 91,
          longitude: -0.1278,
        },
      })
    ).toBeNull();
  });
});
