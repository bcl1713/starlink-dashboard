import { divIcon } from 'leaflet';
import type { LatLngExpression } from 'leaflet';
import {
  MapContainer,
  Marker,
  Polyline,
  ScaleControl,
  TileLayer,
  Tooltip,
  useMapEvents,
  ZoomControl,
} from 'react-leaflet';
import { useState } from 'react';
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

function MapMeasurement({ active }: { active: boolean }) {
  const [start, setStart] = useState<LatLngExpression | null>(null);
  const [distance, setDistance] = useState<number | null>(null);
  useMapEvents({
    click(event) {
      if (!active) return;
      if (!start) {
        setStart(event.latlng);
        setDistance(null);
        return;
      }
      setDistance(event.latlng.distanceTo(start));
      setStart(null);
    },
  });
  if (!active) return null;
  return (
    <p className="map-measurement" role="status">
      {distance === null
        ? 'Select two points to measure'
        : `Distance ${Math.round(distance)} m`}
    </p>
  );
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
    activeNormal: true,
    activeWarning: true,
    history: true,
    markers: true,
  });
  const [measuring, setMeasuring] = useState(false);
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
  const controls = [
    ['route', 'Planned Route'],
    ['activeNormal', 'Active X-band Link - Normal'],
    ['activeWarning', 'Active X-band Link - Warning'],
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
              checked={visible[key]}
              onChange={() =>
                setVisible((current) => ({ ...current, [key]: !current[key] }))
              }
              type="checkbox"
            />
            {label}
          </label>
        ))}
        <button
          aria-pressed={measuring}
          onClick={() => setMeasuring((current) => !current)}
          type="button"
        >
          Measure distance
        </button>
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
        <ZoomControl position="topright" />
        <ScaleControl imperial={false} />
        <TileLayer attribution="Tiles © Esri" url={ARCGIS_IMAGERY} />

        {visible.route && (
          <>
            <Polyline color="#d97706" positions={route.west} weight={2} />
            <Polyline color="#d97706" positions={route.east} weight={2} />
          </>
        )}
        {visible.activeNormal && (
          <>
            <Polyline
              color="#22c55e"
              positions={activeLinks.normal.west}
              weight={4}
            />
            <Polyline
              color="#22c55e"
              positions={activeLinks.normal.east}
              weight={4}
            />
          </>
        )}
        {visible.activeWarning && (
          <>
            <Polyline
              color="#facc15"
              positions={activeLinks.warning.west}
              weight={4}
            />
            <Polyline
              color="#facc15"
              positions={activeLinks.warning.east}
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
        <MapMeasurement active={measuring} />
      </MapContainer>
      <figcaption>{alternative}</figcaption>
    </figure>
  );
}
