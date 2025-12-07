import type { LatLngExpression, LatLng } from 'leaflet';
import type { XBandTransition } from '../../../types/satellite';
import type { KaTransition } from '../../../types/timeline';

/**
 * Helper function to extract longitude from various coordinate formats
 */
function getLngFromCoordinate(coord: LatLngExpression): number {
  if (Array.isArray(coord)) {
    return coord[1];
  }
  return (coord as LatLng).lng;
}

interface UseRouteRendererProps {
  coordinates: LatLngExpression[];
  normalizedCoordinates: LatLngExpression[];
  isIDLCrossing: boolean;
  xbandTransitions?: XBandTransition[];
  kaTransitions?: KaTransition[];
}

interface UseRouteRendererReturn {
  routeSegments: LatLngExpression[][];
  normalizedXBandTransitions: XBandTransition[];
  normalizedKaTransitions: KaTransition[];
  getWaypointCoordinateIndex: (waypointName: string) => number;
}

/**
 * Custom hook for route rendering logic
 * Handles route segmentation, coordinate normalization for transitions
 */
export function useRouteRenderer({
  coordinates,
  normalizedCoordinates,
  isIDLCrossing,
  xbandTransitions = [],
  kaTransitions = [],
}: UseRouteRendererProps): UseRouteRendererReturn {
  // Find the index in coordinates array that matches a waypoint by name
  const getWaypointCoordinateIndex = (): number => {
    // Placeholder implementation - returns -1 (not found)
    // This function is kept for backward compatibility but unused in current implementation
    return -1;
  };

  // Split route into segments at International Date Line crossings
  const getRouteSegments = (
    coords: LatLngExpression[]
  ): LatLngExpression[][] => {
    if (coords.length === 0) return [];

    const segments: LatLngExpression[][] = [];
    let currentSegment: LatLngExpression[] = [coords[0]];

    for (let i = 1; i < coords.length; i++) {
      const prev = coords[i - 1];
      const curr = coords[i];

      const prevLng = getLngFromCoordinate(prev);
      const currLng = getLngFromCoordinate(curr);

      // Check if this segment crosses the International Date Line (IDL)
      if (Math.abs(currLng - prevLng) > 180) {
        // IDL crossing detected - finish current segment and start new one
        segments.push(currentSegment);
        currentSegment = [curr];
      } else {
        // Normal segment - add point to current segment
        currentSegment.push(curr);
      }
    }

    // Add the final segment
    if (currentSegment.length > 0) {
      segments.push(currentSegment);
    }

    return segments;
  };

  // Calculate route segments based on whether we need normalization
  const routeSegments = getRouteSegments(
    isIDLCrossing ? normalizedCoordinates : coordinates
  );

  // Normalize X-Band transition coordinates to match route coordinate system
  const normalizedXBandTransitions = (() => {
    if (!isIDLCrossing) {
      return xbandTransitions; // No normalization needed for non-IDL routes
    }

    // Normalize to 0-360 range for IDL-crossing routes
    return xbandTransitions.map((t) => ({
      ...t,
      longitude: t.longitude < 0 ? t.longitude + 360 : t.longitude,
    }));
  })();

  // Normalize Ka transition coordinates to match route coordinate system
  const normalizedKaTransitions = (() => {
    if (!isIDLCrossing) {
      return kaTransitions; // No normalization needed for non-IDL routes
    }

    // Normalize to 0-360 range for IDL-crossing routes
    return kaTransitions.map((t) => ({
      ...t,
      longitude: t.longitude < 0 ? t.longitude + 360 : t.longitude,
    }));
  })();

  return {
    routeSegments,
    normalizedXBandTransitions,
    normalizedKaTransitions,
    getWaypointCoordinateIndex,
  };
}
