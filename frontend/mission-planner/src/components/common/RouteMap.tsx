import { MapContainer, TileLayer, Polyline } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngExpression, LatLngBoundsExpression } from 'leaflet';

interface RouteMapProps {
  coordinates: LatLngExpression[];
  height?: string;
}

export function RouteMap({ coordinates, height = '400px' }: RouteMapProps) {
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
          <Polyline positions={coordinates} color="blue" weight={3} />
        </MapContainer>
      ) : (
        <div className="flex items-center justify-center h-full bg-gray-100 rounded-lg">
          <p className="text-gray-500">No route data available</p>
        </div>
      )}
    </div>
  );
}
