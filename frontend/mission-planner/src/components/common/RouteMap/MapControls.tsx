import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import type { Map, LatLngBoundsExpression } from 'leaflet';
import { logger } from '../../../utils/logger';

interface MapControlsProps {
  bounds: LatLngBoundsExpression | undefined;
  mapRef: React.MutableRefObject<Map | null>;
  coordinateCount: number;
}

/**
 * Component to handle map interactions and fit bounds
 */
export function MapControls({
  bounds,
  mapRef,
  coordinateCount,
}: MapControlsProps) {
  const map = useMap();

  useEffect(() => {
    mapRef.current = map;
    if (bounds && coordinateCount > 0) {
      try {
        // Automatic fitting must complete before this route map can unmount.
        map.fitBounds(bounds, { padding: [50, 50], animate: false });
      } catch (error) {
        logger.warn('Could not fit bounds to map:', error);
      }
    }
  }, [map, bounds, mapRef, coordinateCount]);

  return null;
}
