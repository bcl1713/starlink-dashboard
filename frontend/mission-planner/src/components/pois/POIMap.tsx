import { useRef } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMapEvent,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { POI } from '../../services/pois';

interface POIMapProps {
  pois?: POI[];
  onMapClick?: (lat: number, lng: number) => void;
  onPOIClick?: (poi: POI) => void;
  center?: [number, number];
  zoom?: number;
}

// Fix for Leaflet default icon issue
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

function MapClickHandler({
  onMapClick,
}: {
  onMapClick?: (lat: number, lng: number) => void;
}) {
  useMapEvent('click', (e) => {
    onMapClick?.(e.latlng.lat, e.latlng.lng);
  });
  return null;
}

export function POIMap({
  pois = [],
  onMapClick,
  onPOIClick,
  center = [0, 0],
  zoom = 3,
}: POIMapProps) {
  const mapRef = useRef(null);

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ width: '100%', height: '100%', borderRadius: '0.5rem' }}
      ref={mapRef}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />

      {onMapClick && <MapClickHandler onMapClick={onMapClick} />}

      {pois?.map((poi) => (
        <Marker
          key={poi.id}
          position={[poi.latitude, poi.longitude]}
          eventHandlers={{
            click: () => onPOIClick?.(poi),
          }}
        >
          <Popup>
            <div className="space-y-2">
              <p className="font-semibold">{poi.name}</p>
              {poi.category && (
                <p className="text-sm text-gray-600">{poi.category}</p>
              )}
              {poi.description && <p className="text-sm">{poi.description}</p>}
              <p className="text-xs text-gray-500">
                {poi.latitude.toFixed(4)}, {poi.longitude.toFixed(4)}
              </p>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
