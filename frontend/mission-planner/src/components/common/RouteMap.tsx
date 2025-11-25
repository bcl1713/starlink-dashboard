import { useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngExpression, LatLngBoundsExpression, Map } from 'leaflet';
import type { XBandTransition, KaOutage, KuOutageOverride } from '../../types/satellite';
import type { AARSegment } from '../../types/aar';
import type { Waypoint } from '../../services/routes';
import type { KaTransition } from '../../types/timeline';

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
  waypoints = [],
  waypointObjects = []
}: RouteMapProps) {
  const mapRef = useRef<Map>(null);

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

  // Calculate haversine distance between two points in meters
  const haversineDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
    const R = 6371000; // Earth's radius in meters
    const toRad = (deg: number) => (deg * Math.PI) / 180;

    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  };

  // Find the index in coordinates array that matches a waypoint by name
  // Uses the waypointObjects to find the actual coordinates, then matches to closest point
  const getWaypointCoordinateIndex = (waypointName: string): number => {
    if (!waypointName || waypoints.length === 0 || coordinates.length === 0) return -1;

    // First, find the waypoint object by name
    const normalizedName = waypointName.trim().toLowerCase();
    const waypointObj = waypointObjects.find(wp => (wp.name || '').trim().toLowerCase() === normalizedName);

    if (!waypointObj) {
      console.warn(`Waypoint object not found: "${waypointName}"`);
      return -1;
    }

    console.log(`Found waypoint "${waypointName}" at [${waypointObj.latitude}, ${waypointObj.longitude}]`);

    // Now find the closest coordinate to this waypoint
    let closestIndex = 0;
    let minDistance = Number.MAX_SAFE_INTEGER;

    for (let i = 0; i < coordinates.length; i++) {
      const coord = coordinates[i];
      const [lat, lon] = Array.isArray(coord)
        ? [coord[0], coord[1]]
        : [(coord as any).lat, (coord as any).lng];

      const distance = haversineDistance(waypointObj.latitude, waypointObj.longitude, lat, lon);

      if (distance < minDistance) {
        minDistance = distance;
        closestIndex = i;
      }
    }

    console.log(`Matched waypoint to coordinate index ${closestIndex} (distance: ${minDistance.toFixed(0)}m)`);
    return closestIndex;
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

  // Normalize X-Band transition coordinates to match route coordinate system
  const normalizedXBandTransitions = (() => {
    if (!detectIDLCrossing()) {
      return xbandTransitions; // No normalization needed for non-IDL routes
    }

    // Normalize to 0-360 range for IDL-crossing routes
    return xbandTransitions.map(t => ({
      ...t,
      longitude: t.longitude < 0 ? t.longitude + 360 : t.longitude
    }));
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
            {normalizedXBandTransitions.map((transition) => {
              console.log('Rendering X-Band transition marker:', transition);
              return (
                <Marker
                  key={`xband-${transition.id}`}
                  position={[transition.latitude, transition.longitude]}
                  icon={createXBandIcon()}
                >
                  <Popup>
                    X-Band Transition to {transition.target_satellite_id}
                  </Popup>
                </Marker>
              );
            })}

            {/* Render Ka transition markers */}
            {kaTransitions?.map((transition, idx) => (
              <Marker
                key={`ka-${idx}`}
                position={[transition.latitude, transition.longitude]}
                icon={createKaIcon()}
              >
                <Popup>
                  <div>
                    <strong>Ka Transition</strong><br/>
                    From: {transition.fromSatellite}<br/>
                    To: {transition.toSatellite}<br/>
                    Time: {new Date(transition.timestamp).toLocaleString()}
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Render AAR segments */}
            {aarSegments.map((segment, idx) => {
              // DEBUG: Log what we're working with
              console.log(`\n===== AAR Segment ${idx} =====`);
              console.log('Waypoint names:', waypoints);
              console.log('Waypoint objects:', waypointObjects);
              console.log(`Looking for: "${segment.start_waypoint_name}" → "${segment.end_waypoint_name}"`);

              // Find the coordinate indices for this AAR segment
              const startIdx = getWaypointCoordinateIndex(segment.start_waypoint_name);
              const endIdx = getWaypointCoordinateIndex(segment.end_waypoint_name);

              console.log(`Found coordinate indices: startIdx=${startIdx}, endIdx=${endIdx}`);
              console.log(`Total waypoint objects: ${waypointObjects.length}`);
              console.log(`Total coordinates: ${coordinates.length}`);

              // Skip if waypoints not found
              if (startIdx === -1 || endIdx === -1) {
                console.warn(
                  `AAR segment ${idx}: Could not find waypoints "${segment.start_waypoint_name}" or "${segment.end_waypoint_name}"`
                );
                console.log('Available waypoint names:', waypoints);
                return null;
              }

              // Ensure valid order
              if (startIdx > endIdx) {
                console.warn(
                  `AAR segment ${idx}: Start waypoint at index ${startIdx} is after end waypoint at index ${endIdx}`
                );
                return null;
              }

              // Get the correct coordinate array (use normalized for IDL routes)
              const useNormalized = detectIDLCrossing();
              const coordsToUse = useNormalized ? normalizedCoordinates : coordinates;
              const segmentCoordinates = coordsToUse.slice(startIdx, endIdx + 1);

              console.log(`Using ${useNormalized ? 'normalized' : 'original'} coordinates`);
              console.log(`Slicing coords from index ${startIdx} to ${endIdx} (inclusive)`);
              console.log(`Segment coordinates count: ${segmentCoordinates.length}`);
              if (segmentCoordinates.length <= 10) {
                console.log('Segment coordinates:', segmentCoordinates);
              } else {
                console.log(`Segment coordinates: [${segmentCoordinates.length} points, first 3 and last 3]`, {
                  first3: segmentCoordinates.slice(0, 3),
                  last3: segmentCoordinates.slice(-3),
                });
              }

              // Skip if no coordinates found
              if (segmentCoordinates.length === 0) {
                console.warn(`AAR segment ${idx}: No coordinates found for slice [${startIdx}:${endIdx + 1}]`);
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
