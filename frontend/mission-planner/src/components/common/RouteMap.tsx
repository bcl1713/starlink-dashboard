import { useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngExpression, LatLngBoundsExpression, Map } from 'leaflet';
import type { XBandTransition, KaOutage, KuOutageOverride } from '../../types/satellite';
import type { AARSegment } from '../../types/aar';

interface RouteMapProps {
  coordinates: LatLngExpression[];
  height?: string;
  xbandTransitions?: XBandTransition[];
  aarSegments?: AARSegment[];
  kaOutages?: KaOutage[];
  kuOutages?: KuOutageOverride[];
}

export function RouteMap({
  coordinates,
  height = '400px',
  xbandTransitions = [],
  aarSegments = [],
  kaOutages = [],
  kuOutages = []
}: RouteMapProps) {
  const mapRef = useRef<Map>(null);

  // Create X-Band transition icon
  const createXBandIcon = () => {
    return L.divIcon({
      className: 'xband-marker',
      html: '<div class="w-4 h-4 bg-blue-500 rounded-full border-2 border-white"></div>',
      iconSize: [16, 16],
    });
  };
  // Split route into segments at International Date Line crossings
  const getRouteSegments = (): LatLngExpression[][] => {
    if (coordinates.length === 0) return [];

    const segments: LatLngExpression[][] = [];
    let currentSegment: LatLngExpression[] = [coordinates[0]];

    for (let i = 1; i < coordinates.length; i++) {
      const prev = coordinates[i - 1];
      const curr = coordinates[i];

      // Extract longitude values
      const prevLng = Array.isArray(prev) ? prev[1] : (prev as any).lng;
      const currLng = Array.isArray(curr) ? curr[1] : (curr as any).lng;

      // Check if this segment crosses the International Date Line (IDL)
      // If longitude difference > 180°, it's crossing the IDL
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

  // Detect if route crosses International Date Line
  const detectIDLCrossing = (): boolean => {
    for (let i = 1; i < coordinates.length; i++) {
      const prev = coordinates[i - 1];
      const curr = coordinates[i];
      const prevLng = Array.isArray(prev) ? prev[1] : (prev as any).lng;
      const currLng = Array.isArray(curr) ? curr[1] : (curr as any).lng;
      if (Math.abs(currLng - prevLng) > 180) {
        return true;
      }
    }
    return false;
  };

  // Calculate bounds from coordinates with IDL handling
  const getBounds = (): LatLngBoundsExpression | undefined => {
    if (coordinates.length === 0) return undefined;

    const lats = coordinates.map((coord) => {
      if (Array.isArray(coord)) return coord[0];
      return (coord as { lat: number; lng: number }).lat;
    });
    const lngs = coordinates.map((coord) => {
      if (Array.isArray(coord)) return coord[1];
      return (coord as { lat: number; lng: number }).lng;
    });

    const isIDLCrossing = detectIDLCrossing();

    if (isIDLCrossing) {
      // Normalize longitudes to 0-360 range for IDL crossing routes
      const normLngs = lngs.map(lng => lng < 0 ? lng + 360 : lng);
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

    const lats = coordinates.map((coord) => {
      if (Array.isArray(coord)) return coord[0];
      return (coord as { lat: number; lng: number }).lat;
    });
    const lngs = coordinates.map((coord) => {
      if (Array.isArray(coord)) return coord[1];
      return (coord as { lat: number; lng: number }).lng;
    });

    const isIDLCrossing = detectIDLCrossing();

    if (isIDLCrossing) {
      // Normalize longitudes for center calculation
      const normLngs = lngs.map(lng => lng < 0 ? lng + 360 : lng);
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

  const bounds = getBounds();
  const center = getCenter();
  const routeSegments = getRouteSegments();

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

  // For IDL-crossing routes, we need to normalize coordinates to be on same side
  const normalizedCoordinates = (() => {
    if (!detectIDLCrossing()) return coordinates;

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

  // Recalculate segments with normalized coordinates
  const normalizedSegments = (() => {
    if (normalizedCoordinates.length === 0) return [];

    const segments: LatLngExpression[][] = [];
    let currentSegment: LatLngExpression[] = [normalizedCoordinates[0]];

    for (let i = 1; i < normalizedCoordinates.length; i++) {
      const prev = normalizedCoordinates[i - 1];
      const curr = normalizedCoordinates[i];

      const prevLng = Array.isArray(prev) ? prev[1] : (prev as any).lng;
      const currLng = Array.isArray(curr) ? curr[1] : (curr as any).lng;

      // Still check for wrapping (now in 0-360 space, look for > 180 jumps)
      if (Math.abs(currLng - prevLng) > 180) {
        segments.push(currentSegment);
        currentSegment = [curr];
      } else {
        currentSegment.push(curr);
      }
    }

    if (currentSegment.length > 0) {
      segments.push(currentSegment);
    }

    return segments;
  })();

  // Component to handle map interactions
  function MapController({ bounds: mapBounds }: { bounds: LatLngBoundsExpression | undefined }) {
    const map = useMap();

    useEffect(() => {
      mapRef.current = map;
      if (mapBounds && coordinates.length > 0) {
        try {
          map.fitBounds(mapBounds, { padding: [50, 50] });
        } catch (error) {
          console.warn('Could not fit bounds to map:', error);
        }
      }
    }, [map, mapBounds]);

    return null;
  }

  return (
    <div>
      <div style={{ height, width: '100%' }}>
        {coordinates.length > 0 ? (
          <MapContainer
            bounds={bounds}
            center={center}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={false}
            worldCopyJump={true}
          >
            <MapController bounds={bounds} />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {/* Render normalized segments for IDL routes, original segments otherwise */}
            {(detectIDLCrossing() ? normalizedSegments : routeSegments).map((segment, idx) => (
              <Polyline
                key={idx}
                positions={segment}
                color="blue"
                weight={3}
              />
            ))}

            {/* Render X-Band transition markers */}
            {xbandTransitions.map((transition, idx) => (
              <Marker
                key={`xband-${idx}`}
                position={[transition.latitude, transition.longitude]}
                icon={createXBandIcon()}
              >
                <Popup>
                  X-Band Transition to {transition.target_satellite_id}
                </Popup>
              </Marker>
            ))}

            {/* Render AAR segments */}
            {aarSegments.map((segment, idx) => {
              // For AAR visualization, we'll render a green overlay across the segment
              // Since we don't have waypoint names in the coordinates array,
              // we render the entire coordinates as an AAR segment indicator
              // In a future enhancement, we could match segment names to coordinate indices
              return (
                <Polyline
                  key={`aar-${idx}`}
                  positions={(detectIDLCrossing() ? normalizedSegments : routeSegments).flat() as LatLngExpression[]}
                  color="green"
                  weight={6}
                  opacity={0.6}
                  dashArray="5, 5"
                >
                  <Popup>
                    AAR Segment: {segment.start_waypoint_name} → {segment.end_waypoint_name}
                  </Popup>
                </Polyline>
              );
            })}
          </MapContainer>
        ) : (
          <div className="flex items-center justify-center h-full bg-gray-100 rounded-lg">
            <p className="text-gray-500">No route data available</p>
          </div>
        )}
      </div>

      {/* Outage Information Panel */}
      {(kaOutages.length > 0) || (kuOutages.length > 0) ? (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-2">Communication Outages</h3>

          {kaOutages.length > 0 && (
            <div className="mb-3">
              <h4 className="font-medium text-sm mb-1">Ka-Band Outages</h4>
              {kaOutages.map((outage, idx) => (
                <div key={`ka-${idx}`} className="text-sm text-gray-700 ml-2">
                  • {new Date(outage.start_time).toLocaleString()} ({outage.duration_seconds}s)
                </div>
              ))}
            </div>
          )}

          {kuOutages.length > 0 && (
            <div>
              <h4 className="font-medium text-sm mb-1">Ku-Band Outages</h4>
              {kuOutages.map((outage, idx) => (
                <div key={`ku-${idx}`} className="text-sm text-gray-700 ml-2">
                  • {new Date(outage.start_time).toLocaleString()} ({outage.duration_seconds}s)
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
