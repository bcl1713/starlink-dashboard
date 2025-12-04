import { Polyline, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import type { LatLngExpression } from 'leaflet';
import type { XBandTransition } from '../../../types/satellite';
import type { AARSegment } from '../../../types/aar';
import type { KaTransition } from '../../../types/timeline';

interface RouteLayerProps {
  routeSegments: LatLngExpression[][];
  xbandTransitions: XBandTransition[];
  kaTransitions: KaTransition[];
  aarSegments: AARSegment[];
  getWaypointCoordinateIndex: (waypointName: string) => number;
  coordinates: LatLngExpression[];
  normalizedCoordinates: LatLngExpression[];
  isIDLCrossing: boolean;
}

/**
 * Component that renders all route layers (route lines, markers, AAR segments)
 */
export function RouteLayer({
  routeSegments,
  xbandTransitions,
  kaTransitions,
  aarSegments,
  getWaypointCoordinateIndex,
  normalizedCoordinates,
}: RouteLayerProps) {
  // Create X-Band transition icon
  const createXBandIcon = () => {
    return L.divIcon({
      className: 'xband-marker',
      html: '<div style="width: 16px; height: 16px; background: #3B82F6; border-radius: 50%; border: 2px solid white; box-sizing: border-box;"></div>',
      iconSize: [16, 16],
    });
  };

  // Create Ka transition icon (green)
  const createKaIcon = () => {
    return L.divIcon({
      className: 'ka-marker',
      html: '<div style="width: 16px; height: 16px; background: #10B981; border-radius: 50%; border: 2px solid white; box-sizing: border-box;"></div>',
      iconSize: [16, 16],
    });
  };

  return (
    <>
      {/* Render route segments */}
      {routeSegments.map((segment, idx) => (
        <Polyline key={idx} positions={segment} color="blue" weight={3} />
      ))}

      {/* Render X-Band transition markers */}
      {xbandTransitions.map((transition) => {
        return (
          <Marker
            key={`xband-${transition.id}`}
            position={[transition.latitude, transition.longitude]}
            icon={createXBandIcon()}
          >
            <Popup>X-Band Transition to {transition.target_satellite_id}</Popup>
          </Marker>
        );
      })}

      {/* Render Ka transition markers */}
      {kaTransitions.map((transition, idx) => (
        <Marker
          key={`ka-${idx}`}
          position={[transition.latitude, transition.longitude]}
          icon={createKaIcon()}
        >
          <Popup>
            <div>
              <strong>Ka Transition</strong>
              <br />
              From: {transition.fromSatellite}
              <br />
              To: {transition.toSatellite}
              <br />
              Time: {new Date(transition.timestamp).toLocaleString()}
            </div>
          </Popup>
        </Marker>
      ))}

      {/* Render AAR segments */}
      {aarSegments.map((segment, idx) => {
        // Find the coordinate indices for this AAR segment
        const startIdx = getWaypointCoordinateIndex(
          segment.start_waypoint_name
        );
        const endIdx = getWaypointCoordinateIndex(segment.end_waypoint_name);

        // Skip if waypoints not found
        if (startIdx === -1 || endIdx === -1) {
          // eslint-disable-next-line no-console
          console.warn(
            `AAR segment ${idx}: Could not find waypoints "${segment.start_waypoint_name}" or "${segment.end_waypoint_name}"`
          );
          return null;
        }

        // Ensure valid order
        if (startIdx > endIdx) {
          // eslint-disable-next-line no-console
          console.warn(
            `AAR segment ${idx}: Start waypoint at index ${startIdx} is after end waypoint at index ${endIdx}`
          );
          return null;
        }

        // Get the correct coordinate array (use normalized for IDL routes)
        const segmentCoordinates = normalizedCoordinates.slice(
          startIdx,
          endIdx + 1
        );

        // Skip if no coordinates found
        if (segmentCoordinates.length === 0) {
          // eslint-disable-next-line no-console
          console.warn(
            `AAR segment ${idx}: No coordinates found for slice [${startIdx}:${endIdx + 1}]`
          );
          return null;
        }

        return (
          <Polyline
            key={`aar-${idx}`}
            positions={segmentCoordinates}
            color="#FFC107"
            weight={6}
            opacity={0.7}
            dashArray="5, 5"
          >
            <Popup>
              AAR Segment: {segment.start_waypoint_name} →{' '}
              {segment.end_waypoint_name}
            </Popup>
          </Polyline>
        );
      })}
    </>
  );
}
