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

/**
 * Map visualization component showing the route with all overlays
 */
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
    <div className="sticky top-6 h-fit">
      <h2 className="text-xl font-semibold mb-4">Route Visualization</h2>
      <RouteMap
        coordinates={routeCoordinates}
        xbandTransitions={satelliteConfig.xband_transitions}
        kaTransitions={kaTransitions}
        aarSegments={aarConfig.segments}
        kaOutages={satelliteConfig.ka_outages || []}
        kuOutages={satelliteConfig.ku_outages || []}
        waypoints={waypointNames}
        waypointObjects={availableWaypoints}
        timelinePreview={timelinePreview}
        height="600px"
      />
      <div className="mt-4 text-sm text-gray-600 space-y-1">
        <p>• Blue line: Flight route</p>
        <p>• Blue circles: X-Band transition points</p>
        <p>• Green circles: Ka satellite transitions</p>
        <p>• Yellow dashed line: AAR segments</p>
        {timelinePreview && (
          <>
            <p>• Green segments: Nominal communication status</p>
            <p>• Yellow segments: Degraded communication status</p>
            <p>• Red segments: Critical communication status</p>
          </>
        )}
        <p>• See below map for Ka/Ku outage timeline</p>
      </div>
    </div>
  );
}
