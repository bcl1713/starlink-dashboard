import { divIcon } from 'leaflet';
import type { LatLngExpression } from 'leaflet';
import {
  MapContainer,
  Marker,
  Polyline,
  ScaleControl,
  TileLayer,
  Tooltip,
  useMap,
  ZoomControl,
} from 'react-leaflet';
import { useEffect, useState } from 'react';
import 'leaflet/dist/leaflet.css';

export interface MapMarker {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

type LineSegments = { west: LatLngExpression[]; east: LatLngExpression[] };
interface Props {
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  heading?: number;
  route?: LineSegments;
  activeLinks?: { normal: LineSegments; warning: LineSegments };
  history?: LineSegments;
  markers?: {
    flightRoute: MapMarker[];
    satellites: MapMarker[];
    missionEvents: MapMarker[];
  };
  groundEntryPoint?: {
    display: string;
    latitude: number;
    longitude: number;
  } | null;
}

const ARCGIS_IMAGERY =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

function safeCoordinates(latitude: number, longitude: number) {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (latitude < -90 || latitude > 90) return null;
  return {
    latitude,
    longitude: ((((longitude + 180) % 360) + 360) % 360) - 180,
  };
}

function pointIcon(kind: string, rotation = 0) {
  return divIcon({
    className: `operations-map-marker operations-map-marker--${kind}`,
    html: `<span style="transform:rotate(${rotation}deg)">${
      kind === 'aircraft' ? '✈' : '●'
    }</span>`,
    iconAnchor: [12, 12],
    iconSize: [24, 24],
  });
}

function MapMarkers({
  items,
  kind,
}: {
  items: MapMarker[];
  kind: 'route' | 'satellite' | 'event';
}) {
  return items.map((item) => (
    <Marker
      icon={pointIcon(kind)}
      key={`${kind}-${item.id}`}
      position={[item.latitude, item.longitude]}
    >
      <Tooltip>{item.name}</Tooltip>
    </Marker>
  ));
}

function MapSizeInvalidator() {
  const map = useMap();

  useEffect(() => {
    const invalidate = () => map.invalidateSize({ pan: false });
    const frame = requestAnimationFrame(invalidate);
    const observer = new ResizeObserver(invalidate);
    observer.observe(map.getContainer());

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [map]);

  return null;
}

export function CurrentPositionMap({
  latitude,
  longitude,
  heading = 0,
  route = { west: [], east: [] },
  activeLinks = {
    normal: { west: [], east: [] },
    warning: { west: [], east: [] },
  },
  history = { west: [], east: [] },
  markers = { flightRoute: [], satellites: [], missionEvents: [] },
  groundEntryPoint = null,
}: Props) {
  const [visible, setVisible] = useState({
    route: true,
    activeLink: true,
    history: true,
    markers: true,
  });
  const position =
    latitude === null ||
    latitude === undefined ||
    longitude === null ||
    longitude === undefined
      ? null
      : safeCoordinates(latitude, longitude);
  if (!position) return <p>Position unavailable</p>;

  const center: LatLngExpression = [position.latitude, position.longitude];
  const alternative = `Current position: ${position.latitude.toFixed(4)}, ${position.longitude.toFixed(4)}`;
  const hasWarningLink =
    activeLinks.warning.west.length > 0 || activeLinks.warning.east.length > 0;
  const activeLink = hasWarningLink
    ? { color: '#facc15', segments: activeLinks.warning, state: 'Warning' }
    : { color: '#22c55e', segments: activeLinks.normal, state: 'Normal' };
  const controls = [
    ['route', 'Planned Route'],
    ['activeLink', 'Active X-band Link'],
    ['history', 'Position History'],
    ['markers', 'Flight route markers, satellites, and mission events'],
  ] as const;

  return (
    <figure className="current-position-map">
      <fieldset className="operations-map-layers">
        <legend>Operational map layers</legend>
        {controls.map(([key, label]) => (
          <label key={key}>
            <input
              aria-describedby={
                key === 'activeLink' ? 'active-link-status' : undefined
              }
              checked={visible[key]}
              onChange={() =>
                setVisible((current) => ({ ...current, [key]: !current[key] }))
              }
              type="checkbox"
            />
            {label}
          </label>
        ))}
        <p id="active-link-status" role="status">
          Active X-band Link status: {activeLink.state}
        </p>
      </fieldset>
      <MapContainer
        aria-label={alternative}
        center={center}
        className="operations-tile-map"
        keyboard
        scrollWheelZoom
        touchZoom
        worldCopyJump
        zoom={4}
        zoomControl={false}
      >
        <MapSizeInvalidator />
        <ZoomControl position="topright" />
        <ScaleControl imperial={false} />
        <TileLayer attribution="Tiles © Esri" url={ARCGIS_IMAGERY} />

        {visible.route && (
          <>
            <Polyline color="#d97706" positions={route.west} weight={2} />
            <Polyline color="#d97706" positions={route.east} weight={2} />
          </>
        )}
        {visible.activeLink && (
          <>
            <Polyline
              color={activeLink.color}
              positions={activeLink.segments.west}
              weight={4}
            />
            <Polyline
              color={activeLink.color}
              positions={activeLink.segments.east}
              weight={4}
            />
          </>
        )}
        {visible.history && (
          <>
            <Polyline
              color="#3b82f6"
              opacity={0.7}
              positions={history.west}
              weight={3}
            />
            <Polyline
              color="#3b82f6"
              opacity={0.7}
              positions={history.east}
              weight={3}
            />
          </>
        )}
        {visible.markers && (
          <>
            <MapMarkers items={markers.flightRoute} kind="route" />
            <MapMarkers items={markers.satellites} kind="satellite" />
            <MapMarkers items={markers.missionEvents} kind="event" />
          </>
        )}
        {groundEntryPoint && (
          <Marker
            icon={pointIcon('gep')}
            position={[groundEntryPoint.latitude, groundEntryPoint.longitude]}
          >
            <Tooltip>{groundEntryPoint.display}</Tooltip>
          </Marker>
        )}
        <Marker icon={pointIcon('aircraft', heading)} position={center}>
          <Tooltip>Current Position — Heading {heading}°</Tooltip>
        </Marker>
      </MapContainer>
      <figcaption>{alternative}</figcaption>
    </figure>
  );
}
