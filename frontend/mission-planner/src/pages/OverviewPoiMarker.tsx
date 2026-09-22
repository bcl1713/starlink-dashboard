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
  labelOffset?: readonly [number, number];
  hideLabel?: boolean;
  fallbackLabel?: string;
}

export function OverviewPoiMarker({
  poi,
  color,
  globeOccluder,
  labelOffset = [0, 0],
  hideLabel = false,
  fallbackLabel,
}: OverviewPoiMarkerProps) {
  const coordinate = { latitude: poi.latitude, longitude: poi.longitude };

  return (
    <>
      <StarMarker coordinate={coordinate} color={color} size={0.1} />
      {!hideLabel && (
        <Html
          occlude={[globeOccluder]}
          position={globePosition(
            poi.latitude,
            poi.longitude,
            ROUTE_OVERLAY_RADIUS
          )}
          zIndexRange={[0, 0]}
        >
          <span
            className="globe-marker-label"
            data-poi-label={poi.poi_id}
            data-poi-label-offset={`${labelOffset[0]},${labelOffset[1]}`}
            data-poi-label-fallback={fallbackLabel ? 'true' : undefined}
            style={{
              transform: `translate(${labelOffset[0]}px, ${labelOffset[1]}px)`,
            }}
          >
            {fallbackLabel ?? poi.name}
          </span>
        </Html>
      )}
    </>
  );
}
