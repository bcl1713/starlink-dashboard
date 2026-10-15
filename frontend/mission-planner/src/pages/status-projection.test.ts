import { describe, expect, it } from 'vitest';
import {
  projectAircraftPosition,
  projectGroundEntryPoint,
} from './status-projection.ts';

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

  it('returns null when longitude is outside the geographic range', () => {
    expect(
      projectAircraftPosition({
        position: {
          latitude: 51.5074,
          longitude: 181,
        },
      })
    ).toBeNull();
  });

  it('returns null when latitude is not finite', () => {
    expect(
      projectAircraftPosition({
        position: {
          latitude: Number.NaN,
          longitude: -0.1278,
        },
      })
    ).toBeNull();
  });

  it('returns null when longitude is not finite', () => {
    expect(
      projectAircraftPosition({
        position: {
          latitude: 51.5074,
          longitude: Number.NaN,
        },
      })
    ).toBeNull();
  });
  it('projects a valid current ground entry point', () => {
    expect(
      projectGroundEntryPoint({
        ground_entry_point: {
          latitude: 41.2565,
          longitude: -95.9345,
        },
      })
    ).toEqual({
      latitude: 41.2565,
      longitude: -95.9345,
    });
  });

  it('returns null when no ground entry point is available', () => {
    expect(projectGroundEntryPoint({})).toBeNull();
  });

  it('returns null when ground entry point coordinates are invalid', () => {
    expect(
      projectGroundEntryPoint({
        ground_entry_point: {
          latitude: 91,
          longitude: -95.9345,
        },
      })
    ).toBeNull();
  });
});
