import { MapContainer, TileLayer, Polyline } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngExpression, LatLngBoundsExpression } from 'leaflet';

interface RouteMapProps {
  coordinates: LatLngExpression[];
  height?: string;
}

export function RouteMap({ coordinates, height = '400px' }: RouteMapProps) {
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

  // Calculate bounds from coordinates
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

    return [
      [Math.min(...lats), Math.min(...lngs)],
      [Math.max(...lats), Math.max(...lngs)],
    ];
  };

  const bounds = getBounds();
  const center: LatLngExpression =
    coordinates.length > 0 ? coordinates[0] : [0, 0];
  const routeSegments = getRouteSegments();

  return (
    <div style={{ height, width: '100%' }}>
      {coordinates.length > 0 ? (
        <MapContainer
          bounds={bounds}
          center={center}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {/* Render each segment separately to avoid wrapping around the globe */}
          {routeSegments.map((segment, idx) => (
            <Polyline
              key={idx}
              positions={segment}
              color="blue"
              weight={3}
            />
          ))}
        </MapContainer>
      ) : (
        <div className="flex items-center justify-center h-full bg-gray-100 rounded-lg">
          <p className="text-gray-500">No route data available</p>
        </div>
      )}
    </div>
  );
}
