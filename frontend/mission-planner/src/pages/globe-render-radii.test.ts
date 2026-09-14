import { describe, expect, it } from 'vitest';
import { CONFIGURED_GEO_SCENE_RADIUS } from './x-band-satellites-projection';
import {
  GEO_ANALYSIS_CAMERA_POSITION,
  GEO_ANALYSIS_MAX_DISTANCE,
} from './globe-render-radii';

describe('GEO analysis camera model', () => {
  it('frames the configured GEO scene radius with deliberate interaction headroom', () => {
    expect(CONFIGURED_GEO_SCENE_RADIUS).toBe(13.234);
    expect(GEO_ANALYSIS_CAMERA_POSITION).toEqual([0, 0, 22]);
    expect(GEO_ANALYSIS_MAX_DISTANCE).toBe(28);
    expect(GEO_ANALYSIS_CAMERA_POSITION[2]).toBeGreaterThan(
      CONFIGURED_GEO_SCENE_RADIUS
    );
  });
});
