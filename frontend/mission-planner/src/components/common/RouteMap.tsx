import { useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Polyline,
  Popup,
  Marker,
  Tooltip,
} from 'react-leaflet';
import { divIcon } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngExpression } from 'leaflet';
import type {
  XBandTransition,
  KaOutage,
  KuOutageOverride,
} from '../../types/satellite';
import type { AARSegment, ManualAARTrack } from '../../types/aar';
import type { Waypoint } from '../../services/routes';
import type { KaTransition } from '../../types/timeline';
import type { Timeline } from '../../services/timeline';
import type { DerivedRouteEstimate } from '../../services/timeline';
import { useMapState } from './RouteMap/useMapState';
import { useRouteRenderer } from './RouteMap/useRouteRenderer';
import { MapControls } from './RouteMap/MapControls';
import { MapLegend } from './RouteMap/MapLegend';
import { RouteLayer } from './RouteMap/RouteLayer';
import { ColorCodedRoute } from './RouteMap/ColorCodedRoute';
import { formatTime24Hour } from '@/lib/utils';
import { PoiLayerControls } from './PoiLayerControls';
import {
  missionPoiLayer,
  missionPoiVisible,
  type MissionPoiVisibility,
} from '@/lib/mission-poi-layers';
import { draftEventPois } from './RouteMap/eventPois';

function eventIcon(kind: string) {
  const colors = {
    flight_events_enabled: 'var(--route-air-refuel, #d97706)',
    x_band_events_enabled: 'var(--route-handoff, #9333ea)',
    ka_events_enabled: 'var(--route-transition, #16a34a)',
    starshield_events_enabled: 'var(--route-manual-track, #0d9488)',
  };
  const color = colors[missionPoiLayer(kind) ?? 'flight_events_enabled'];
  return divIcon({
    className: 'mission-event-marker',
    html: `<span style="display:block;width:14px;height:14px;border:2px solid white;border-radius:50%;background:${color}"></span>`,
    iconSize: [14, 14],
  });
}

interface RouteMapProps {
  anchoredARSpans?: Array<{
    id: string;
    label: string;
    coordinates: [number, number][];
  }>;
  coordinates: LatLngExpression[];
  height?: string;
  xbandTransitions?: XBandTransition[];
  kaTransitions?: KaTransition[];
  aarSegments?: AARSegment[];
  manualAARTracks?: ManualAARTrack[];
  kaOutages?: KaOutage[];
  kuOutages?: KuOutageOverride[];
  waypoints?: string[];
  waypointObjects?: Waypoint[];
  timelinePreview?: Timeline | null;
  derivedRouteEstimate?: DerivedRouteEstimate | null;
}

export function RouteMap({
  anchoredARSpans = [],
  coordinates,
  height = '400px',
  xbandTransitions = [],
  kaTransitions = [],
  aarSegments = [],
  manualAARTracks = [],
  kaOutages = [],
  kuOutages = [],
  waypointObjects = [],
  timelinePreview = null,
  derivedRouteEstimate = null,
}: RouteMapProps) {
  const [poiVisibility, setPoiVisibility] = useState<MissionPoiVisibility>({});
  const resolvedPois = timelinePreview?.map_pois;
  const eventPois =
    resolvedPois ??
    draftEventPois({
      coordinates: coordinates || [],
      spans: anchoredARSpans,
      windows: aarSegments,
      waypoints: waypointObjects,
      tracks: manualAARTracks,
      timeline: timelinePreview,
      kaOutages,
      kuOutages,
    });
  const { mapRef, bounds, center, isIDLCrossing, normalizedCoordinates } =
    useMapState({ coordinates: coordinates || [] });
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

  if (!coordinates || coordinates.length === 0) {
    return (
      <div style={{ height, width: '100%' }}>
        <div className="flex h-full items-center justify-center rounded-lg border border-border bg-muted">
          <p className="text-muted-foreground">No route data available</p>
        </div>
      </div>
    );
  }

  if (!bounds || !center || routeSegments.length === 0) {
    return (
      <div style={{ height, width: '100%' }}>
        <div className="flex h-full items-center justify-center rounded-lg border border-border bg-muted">
          <p className="text-muted-foreground">Error loading route map</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3">
        <PoiLayerControls
          value={poiVisibility}
          onChange={(field, enabled) =>
            setPoiVisibility((current) => ({ ...current, [field]: enabled }))
          }
        />
      </div>
      <div
        className="relative overflow-hidden rounded-xl border border-border bg-muted shadow-sm"
        style={{ height, width: '100%' }}
      >
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
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <RouteLayer
            routeSegments={routeSegments}
            xbandTransitions={
              resolvedPois || poiVisibility.x_band_events_enabled === false
                ? []
                : normalizedXBandTransitions
            }
            kaTransitions={
              resolvedPois || poiVisibility.ka_events_enabled === false
                ? []
                : normalizedKaTransitions
            }
            aarSegments={aarSegments}
            manualAARTracks={manualAARTracks}
            getWaypointCoordinateIndex={getWaypointCoordinateIndex}
            coordinates={coordinates}
            normalizedCoordinates={normalizedCoordinates}
            isIDLCrossing={isIDLCrossing}
            derivedRouteEstimate={derivedRouteEstimate}
          />
          {eventPois
            .filter((poi) => missionPoiVisible(poi.kind, poiVisibility))
            .map((poi, index) => (
              <Marker
                key={`${poi.kind}-${index}`}
                title={poi.name.replace(/\s+/g, ' ')}
                position={[
                  poi.latitude,
                  isIDLCrossing && poi.longitude < 0
                    ? poi.longitude + 360
                    : poi.longitude,
                ]}
                icon={eventIcon(poi.kind)}
              >
                <Tooltip>{poi.name.replace(/\s+/g, ' ')}</Tooltip>
                <Popup>
                  <strong>{poi.name.replace(/\s+/g, ' ')}</strong>
                  {poi.description && <p>{poi.description}</p>}
                  {poi.expected_arrival_time && (
                    <p>{formatTime24Hour(poi.expected_arrival_time)}</p>
                  )}
                </Popup>
              </Marker>
            ))}
          <ColorCodedRoute
            timeline={timelinePreview}
            isIDLCrossing={isIDLCrossing}
          />
          {anchoredARSpans.map((span) => (
            <Polyline
              key={span.id}
              positions={span.coordinates.map(
                ([lat, lon]) =>
                  [lat, isIDLCrossing && lon < 0 ? lon + 360 : lon] as [
                    number,
                    number,
                  ]
              )}
              pathOptions={{
                color: 'var(--route-aar, #d97706)',
                weight: 8,
                opacity: 0.8,
              }}
            >
              <Popup>{span.label} · anchored AR route span</Popup>
            </Polyline>
          ))}
        </MapContainer>
        <MapLegend hasTimeline={Boolean(timelinePreview?.segments?.length)} />
      </div>

      {(kaOutages.length > 0 || kuOutages.length > 0) && (
        <section
          className="mt-4 rounded-lg border border-border bg-muted/60 p-4"
          aria-label="Communication outages"
        >
          <h3 className="text-base font-semibold text-foreground">
            Communication Outages
          </h3>
          {kaOutages.length > 0 && (
            <div className="mt-3">
              <h4 className="text-sm font-medium text-foreground">
                Ka-Band Outages
              </h4>
              {kaOutages.map((outage, idx) => (
                <div
                  key={`ka-${idx}`}
                  className="ml-2 text-sm text-muted-foreground"
                >
                  • {formatTime24Hour(outage.start_time)} (
                  {outage.duration_seconds}s)
                </div>
              ))}
            </div>
          )}
          {kuOutages.length > 0 && (
            <div className="mt-3">
              <h4 className="text-sm font-medium text-foreground">
                Ku-Band Outages
              </h4>
              {kuOutages.map((outage, idx) => (
                <div
                  key={`ku-${idx}`}
                  className="ml-2 text-sm text-muted-foreground"
                >
                  • {formatTime24Hour(outage.start_time)} (
                  {outage.duration_seconds}s)
                  {outage.reason && ` - ${outage.reason}`}
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
