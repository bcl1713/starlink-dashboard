import { MapContainer, TileLayer } from 'react-leaflet';
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

interface RouteMapProps {
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
  coordinates,
  height = '400px',
  xbandTransitions = [],
  kaTransitions = [],
  aarSegments = [],
  manualAARTracks = [],
  kaOutages = [],
  kuOutages = [],
  timelinePreview = null,
  derivedRouteEstimate = null,
}: RouteMapProps) {
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
            xbandTransitions={normalizedXBandTransitions}
            kaTransitions={normalizedKaTransitions}
            aarSegments={aarSegments}
            manualAARTracks={manualAARTracks}
            getWaypointCoordinateIndex={getWaypointCoordinateIndex}
            coordinates={coordinates}
            normalizedCoordinates={normalizedCoordinates}
            isIDLCrossing={isIDLCrossing}
            derivedRouteEstimate={derivedRouteEstimate}
          />
          <ColorCodedRoute
            timeline={timelinePreview}
            isIDLCrossing={isIDLCrossing}
          />
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
