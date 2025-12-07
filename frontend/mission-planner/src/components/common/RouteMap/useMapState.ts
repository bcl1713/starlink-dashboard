import { useRef } from 'react';
import type {
  Map,
  LatLngExpression,
  LatLngBoundsExpression,
  LatLng,
} from 'leaflet';

/**
 * Helper function to extract latitude from various coordinate formats
 */
function getLatFromCoordinate(coord: LatLngExpression): number {
  if (Array.isArray(coord)) {
    return coord[0];
  }
  return (coord as LatLng).lat;
}

/**
 * Helper function to extract longitude from various coordinate formats
 */
function getLngFromCoordinate(coord: LatLngExpression): number {
  if (Array.isArray(coord)) {
    return coord[1];
  }
  return (coord as LatLng).lng;
}

interface UseMapStateProps {
  coordinates: LatLngExpression[];
}

interface UseMapStateReturn {
  mapRef: React.MutableRefObject<Map | null>;
  bounds: LatLngBoundsExpression | undefined;
  center: LatLngExpression;
  isIDLCrossing: boolean;
  normalizedCoordinates: LatLngExpression[];
}

/**
 * Custom hook for managing map state and calculations
 * Handles International Date Line (IDL) crossing detection and coordinate normalization
 */
export function useMapState({
  coordinates,
}: UseMapStateProps): UseMapStateReturn {
  const mapRef = useRef<Map>(null);

  // Detect if route crosses International Date Line
  const detectIDLCrossing = (): boolean => {
    for (let i = 1; i < coordinates.length; i++) {
      const prev = coordinates[i - 1];
      const curr = coordinates[i];
      const prevLng = getLngFromCoordinate(prev);
      const currLng = getLngFromCoordinate(curr);
      if (Math.abs(currLng - prevLng) > 180) {
        return true;
      }
    }
    return false;
  };

  const isIDLCrossing = detectIDLCrossing();

  // Calculate bounds from coordinates with IDL handling
  const getBounds = (): LatLngBoundsExpression | undefined => {
    if (coordinates.length === 0) return undefined;

    const lats = coordinates.map(getLatFromCoordinate);
    const lngs = coordinates.map(getLngFromCoordinate);

    if (isIDLCrossing) {
      // Normalize longitudes to 0-360 range for IDL crossing routes
      const normLngs = lngs.map((lng) => (lng < 0 ? lng + 360 : lng));
      const minLng = Math.min(...normLngs);
      const maxLng = Math.max(...normLngs);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);

      // Keep in 0-360 range for Leaflet to display correctly
      return [
        [minLat, minLng],
        [maxLat, maxLng],
      ];
    }

    // Standard route without IDL crossing
    return [
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    ];
  };

  // Calculate center with IDL handling
  const getCenter = (): LatLngExpression => {
    if (coordinates.length === 0) return [0, 0];

    const lats = coordinates.map(getLatFromCoordinate);
    const lngs = coordinates.map(getLngFromCoordinate);

    if (isIDLCrossing) {
      // Normalize longitudes for center calculation
      const normLngs = lngs.map((lng) => (lng < 0 ? lng + 360 : lng));
      const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
      const centerLng = (Math.min(...normLngs) + Math.max(...normLngs)) / 2;

      // Keep in 0-360 range for consistent Pacific view
      return [centerLat, centerLng];
    }

    // Standard center calculation
    const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
    const centerLng = (Math.min(...lngs) + Math.max(...lngs)) / 2;
    return [centerLat, centerLng];
  };

  // Normalize coordinates for IDL-crossing routes
  const normalizedCoordinates = (() => {
    if (!isIDLCrossing) return coordinates;

    // Normalize all coordinates to 0-360 range so they appear on same map side
    return coordinates.map((coord) => {
      if (Array.isArray(coord)) {
        const [lat, lng] = coord;
        return [lat, lng < 0 ? lng + 360 : lng] as [number, number];
      }
      const { lat, lng } = coord as { lat: number; lng: number };
      return { lat, lng: lng < 0 ? lng + 360 : lng };
    });
  })();

  const bounds = getBounds();
  const center = getCenter();

  return {
    mapRef,
    bounds,
    center,
    isIDLCrossing,
    normalizedCoordinates,
  };
}
