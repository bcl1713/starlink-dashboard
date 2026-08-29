import { RouteMap } from '../../components/common/RouteMap';
import type { SatelliteConfig } from '../../types/satellite';
import type { AARConfig } from '../../types/aar';
import type { KaTransition } from '../../types/timeline';
import type { Waypoint } from '../../services/routes';
import type { Timeline } from '../../services/timeline';

interface LegMapVisualizationProps {
  routeCoordinates: [number, number][];
  satelliteConfig: SatelliteConfig;
  aarConfig: AARConfig;
  kaTransitions: KaTransition[];
  waypointNames: string[];
  availableWaypoints: Waypoint[];
  timelinePreview?: Timeline | null;
}

/** Displays the route and operational overlays without changing planning data. */
export function LegMapVisualization({
  routeCoordinates,
  satelliteConfig,
  aarConfig,
  kaTransitions,
  waypointNames,
  availableWaypoints,
  timelinePreview,
}: LegMapVisualizationProps) {
  return (
    <section
      className="min-w-0 lg:sticky lg:top-6 lg:h-fit"
      aria-labelledby="route-map-heading"
    >
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
            Operational workspace
          </p>
          <h2
            id="route-map-heading"
            className="text-xl font-semibold text-foreground"
          >
            Route Visualization
          </h2>
        </div>
        <span className="text-xs text-muted-foreground">
          Open the map legend for layer keys
        </span>
      </div>
      {timelinePreview?.derived_route_estimate?.available && (
        <p className="mb-2 text-xs text-muted-foreground">
          Estimated map layer: derived estimate, not telemetry.
        </p>
      )}
      <RouteMap
        coordinates={routeCoordinates}
        xbandTransitions={satelliteConfig.xband_transitions}
        kaTransitions={kaTransitions}
        aarSegments={aarConfig.segments}
        manualAARTracks={aarConfig.manualTracks}
        kaOutages={satelliteConfig.ka_outages || []}
        kuOutages={satelliteConfig.ku_outages || []}
        waypoints={waypointNames}
        waypointObjects={availableWaypoints}
        timelinePreview={timelinePreview}
        derivedRouteEstimate={timelinePreview?.derived_route_estimate}
        height="clamp(20rem, 50vw, 37.5rem)"
      />
    </section>
  );
}
