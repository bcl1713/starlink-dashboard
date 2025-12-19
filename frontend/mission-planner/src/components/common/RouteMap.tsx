import { MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngExpression } from 'leaflet';
import type {
  XBandTransition,
  KaOutage,
  KuOutageOverride,
} from '../../types/satellite';
import type { AARSegment } from '../../types/aar';
import type { Waypoint } from '../../services/routes';
import type { KaTransition } from '../../types/timeline';
import { useMapState } from './RouteMap/useMapState';
import { useRouteRenderer } from './RouteMap/useRouteRenderer';
import { MapControls } from './RouteMap/MapControls';
import { RouteLayer } from './RouteMap/RouteLayer';

interface RouteMapProps {
  coordinates: LatLngExpression[];
  height?: string;
  xbandTransitions?: XBandTransition[];
  kaTransitions?: KaTransition[];
  aarSegments?: AARSegment[];
  kaOutages?: KaOutage[];
  kuOutages?: KuOutageOverride[];
  waypoints?: string[];
  waypointObjects?: Waypoint[];
}

export function RouteMap({
  coordinates,
  height = '400px',
  xbandTransitions = [],
  kaTransitions = [],
  aarSegments = [],
  kaOutages = [],
  kuOutages = [],
}: RouteMapProps) {
  // Use custom hooks for state and rendering logic (must be called before early returns)
  const { mapRef, bounds, center, isIDLCrossing, normalizedCoordinates } =
    useMapState({
      coordinates: coordinates || [],
    });

  const {
    routeSegments,
    normalizedXBandTransitions,
    normalizedKaTransitions,
    getWaypointCoordinateIndex,
  } = useRouteRenderer({
    coordinates: coordinates || [],
    normalizedCoordinates,
    isIDLCrossing,
    xbandTransitions,
    kaTransitions,
  });

  // Defensive check: ensure we have valid coordinate data
  if (!coordinates || coordinates.length === 0) {
    return (
      <div style={{ height, width: '100%' }}>
        <div className="flex items-center justify-center h-full bg-gray-100 rounded-lg">
          <p className="text-gray-500">No route data available</p>
        </div>
      </div>
    );
  }

  // Defensive check: ensure bounds and center are valid
  if (!bounds || !center || routeSegments.length === 0) {
    return (
      <div style={{ height, width: '100%' }}>
        <div className="flex items-center justify-center h-full bg-gray-100 rounded-lg">
          <p className="text-gray-500">Error loading route map</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ height, width: '100%' }}>
        <MapContainer
          bounds={bounds}
          center={center}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={false}
          worldCopyJump={true}
        >
          <MapControls
            bounds={bounds}
            mapRef={mapRef}
            coordinateCount={coordinates.length}
          />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <RouteLayer
            routeSegments={routeSegments}
            xbandTransitions={normalizedXBandTransitions}
            kaTransitions={normalizedKaTransitions}
            aarSegments={aarSegments}
            getWaypointCoordinateIndex={getWaypointCoordinateIndex}
            coordinates={coordinates}
            normalizedCoordinates={normalizedCoordinates}
            isIDLCrossing={isIDLCrossing}
          />
        </MapContainer>
      </div>

      {/* Outage Information Panel */}
      {kaOutages.length > 0 || kuOutages.length > 0 ? (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-2">Communication Outages</h3>

          {kaOutages.length > 0 && (
            <div className="mb-3">
              <h4 className="font-medium text-sm mb-1">Ka-Band Outages</h4>
              {kaOutages.map((outage, idx) => (
                <div key={`ka-${idx}`} className="text-sm text-gray-700 ml-2">
                  • {new Date(outage.start_time).toLocaleString()} (
                  {outage.duration_seconds}s)
                </div>
              ))}
            </div>
          )}

          {kuOutages.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-1">Ku-Band Outages</h4>
              {kuOutages.map((outage, idx) => (
                <div key={`ku-${idx}`} className="text-sm text-gray-700 ml-2">
                  • {new Date(outage.start_time).toLocaleString()} (
                  {outage.duration_seconds}s)
                  {outage.reason && ` - ${outage.reason}`}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
