const SCENE_EARTH_RADIUS = 2;
const WGS84_SEMI_MAJOR_AXIS_METERS = 6_378_137;
const FEET_TO_METERS = 0.3048;

export const ROUTE_OVERLAY_ALTITUDE_FEET = 10;
export const ROUTE_OVERLAY_RADIUS =
  SCENE_EARTH_RADIUS *
  (1 +
    (ROUTE_OVERLAY_ALTITUDE_FEET * FEET_TO_METERS) /
      WGS84_SEMI_MAJOR_AXIS_METERS);

/**
 * True-scale configured GEO placement uses scene radius 13.234. These controls
 * keep that radius viewable while preserving close globe inspection.
 */
export const GEO_ANALYSIS_CAMERA_POSITION: [number, number, number] = [
  0, 0, 22,
];
export const GEO_ANALYSIS_MAX_DISTANCE = 28;
