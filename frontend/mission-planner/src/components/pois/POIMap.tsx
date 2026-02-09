import { useRef, useEffect } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMapEvent,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { POI, POIWithETA } from '../../services/pois';

// Import marker icons directly so Vite bundles them (avoids CSP issues with CDN)
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

interface POIMapProps {
  pois?: POI[];
  etaData?: POIWithETA[];
  routeCoordinates?: [number, number][];
  onMapClick?: (lat: number, lng: number) => void;
  onPOIClick?: (poi: POI) => void;
  center?: [number, number];
  zoom?: number;
  focusPOI?: POI | null;
}

// Fix for Leaflet default icon issue - use locally bundled icons
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
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

function MapFocusHandler({ focusPOI }: { focusPOI?: POI | null }) {
  const map = useMap();

  useEffect(() => {
    if (focusPOI) {
      map.flyTo([focusPOI.latitude, focusPOI.longitude], 12, {
        duration: 0.5,
      });
    }
  }, [focusPOI, map]);

  return null;
}

export function POIMap({
  pois = [],
  etaData,
  routeCoordinates,
  onMapClick,
  onPOIClick,
  center = [0, 0],
  zoom = 3,
  focusPOI,
}: POIMapProps) {
  const mapRef = useRef(null);

  // Build projection lookup from ETA data
  const projectionMap = new Map<
    string,
    { lat: number; lng: number; status?: string }
  >();
  if (etaData) {
    for (const eta of etaData) {
      const poiId = eta.poi_id || eta.id;
      if (
        eta.projected_latitude != null &&
        eta.projected_longitude != null &&
        eta.is_on_active_route
      ) {
        projectionMap.set(poiId, {
          lat: eta.projected_latitude,
          lng: eta.projected_longitude,
          status: eta.route_aware_status || undefined,
        });
      }
    }
  }

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
      <MapFocusHandler focusPOI={focusPOI} />

      {/* Active route line */}
      {routeCoordinates && routeCoordinates.length > 1 && (
        <Polyline
          positions={routeCoordinates}
          pathOptions={{ color: '#3b82f6', weight: 3, opacity: 0.7 }}
        />
      )}

      {/* Projection lines from POIs to their projected route points */}
      {pois?.map((poi) => {
        const projection = projectionMap.get(poi.id);
        if (!projection) return null;
        return (
          <Polyline
            key={`proj-${poi.id}`}
            positions={[
              [poi.latitude, poi.longitude],
              [projection.lat, projection.lng],
            ]}
            pathOptions={{
              color:
                projection.status === 'already_passed' ? '#9ca3af' : '#8b5cf6',
              weight: 2,
              opacity: 0.6,
              dashArray: '4 6',
            }}
          />
        );
      })}

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
