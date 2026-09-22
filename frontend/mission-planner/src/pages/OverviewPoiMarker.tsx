import { Html } from '@react-three/drei';
import type { RefObject } from 'react';
import type * as THREE from 'three';
import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';
import { globePosition } from './globe-coordinates';
import { ROUTE_OVERLAY_RADIUS } from './globe-render-radii';
import { StarMarker } from './OverviewStarMarker';

interface OverviewPoiMarkerProps {
  poi: OverviewUpcomingPoi;
  color: string;
  globeOccluder: RefObject<THREE.Group>;
}

export function OverviewPoiMarker({
  poi,
  color,
  globeOccluder,
}: OverviewPoiMarkerProps) {
  const coordinate = { latitude: poi.latitude, longitude: poi.longitude };

  return (
    <>
      <StarMarker coordinate={coordinate} color={color} size={0.1} />
      <Html
        occlude={[globeOccluder]}
        position={globePosition(
          poi.latitude,
          poi.longitude,
          ROUTE_OVERLAY_RADIUS
        )}
        zIndexRange={[0, 0]}
      >
        <span className="globe-marker-label">{poi.name}</span>
      </Html>
    </>
  );
}
