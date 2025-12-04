import { useState, useEffect } from 'react';
import type { SatelliteConfig } from '../../types/satellite';
import type { AARConfig } from '../../types/aar';
import type { KaTransition } from '../../types/timeline';
import type { Waypoint } from '../../services/routes';
import { routesApi } from '../../services/routes';
import {
  satelliteService,
  type SatelliteResponse,
} from '../../services/satellites';
import { poisService, type POI } from '../../services/pois';

interface UseLegDataProps {
  routeId?: string;
  missionId?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  legTransports?: any;
}

interface UseLegDataReturn {
  satelliteConfig: SatelliteConfig;
  setSatelliteConfig: React.Dispatch<React.SetStateAction<SatelliteConfig>>;
  aarConfig: AARConfig;
  setAARConfig: React.Dispatch<React.SetStateAction<AARConfig>>;
  routeCoordinates: [number, number][];
  availableWaypoints: Waypoint[];
  waypointNames: string[];
  availableSatellites: string[];
  kaTransitions: KaTransition[];
  hasUnsavedChanges: boolean;
  setHasUnsavedChanges: React.Dispatch<React.SetStateAction<boolean>>;
}

/**
 * Initialize satellite config from leg transports data
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function initializeSatelliteConfig(legTransports?: any): SatelliteConfig {
  if (!legTransports) {
    return {
      xband_starting_satellite: undefined,
      xband_transitions: [],
      ka_outages: [],
      ku_outages: [],
    };
  }
  return {
    xband_starting_satellite: legTransports.initial_x_satellite_id,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    xband_transitions: (legTransports.x_transitions as any[]) || [],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ka_outages: (legTransports.ka_outages as any[]) || [],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ku_outages: (legTransports.ku_overrides as any[]) || [],
  };
}

/**
 * Initialize AAR config from leg transports data
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function initializeAARConfig(legTransports?: any): AARConfig {
  if (!legTransports) {
    return { segments: [] };
  }
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    segments: (legTransports.aar_windows as any[]) || [],
  };
}

/**
 * Custom hook for managing leg data, including routes, satellites, and configurations
 */
export function useLegData({
  routeId,
  missionId,
  legTransports,
}: UseLegDataProps): UseLegDataReturn {
  // State for configurations
  const [satelliteConfig, setSatelliteConfig] = useState<SatelliteConfig>(() =>
    initializeSatelliteConfig(legTransports)
  );

  const [aarConfig, setAARConfig] = useState<AARConfig>(() =>
    initializeAARConfig(legTransports)
  );

  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>(
    []
  );
  const [availableWaypoints, setAvailableWaypoints] = useState<Waypoint[]>([]);
  const [waypointNames, setWaypointNames] = useState<string[]>([]);
  const [availableSatellites, setAvailableSatellites] = useState<string[]>([]);
  const [kaTransitions, setKaTransitions] = useState<KaTransition[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Convert Ka transition POIs to KaTransition format for map display
  const convertPoiToKaTransition = (poi: POI): KaTransition | null => {
    // Try to parse new format: "Ka Transition AOR → POR"
    const newFormatMatch = poi.name.match(
      /Ka\s+Transition\s+(\w+)\s*[\u2192→]\s*(\w+)/i
    );
    if (newFormatMatch) {
      return {
        latitude: poi.latitude,
        longitude: poi.longitude,
        fromSatellite: newFormatMatch[1],
        toSatellite: newFormatMatch[2],
        timestamp: poi.created_at,
      };
    }

    // Fallback to CommKa format check
    if (!poi.name.includes('CommKa')) {
      return null;
    }

    const type = poi.name.split('\n')[1] || 'Swap';
    let fromSat = 'Previous';
    let toSat = 'Next';

    if (type === 'Exit') {
      fromSat = 'Available';
      toSat = 'Unavailable';
    } else if (type === 'Enter') {
      fromSat = 'Unavailable';
      toSat = 'Available';
    }

    return {
      latitude: poi.latitude,
      longitude: poi.longitude,
      fromSatellite: fromSat,
      toSatellite: toSat,
      timestamp: poi.created_at,
    };
  };

  // Load satellites on component mount
  useEffect(() => {
    satelliteService
      .getAll()
      .then((satellites: SatelliteResponse[]) =>
        setAvailableSatellites(
          satellites.map((s: SatelliteResponse) => s.satellite_id)
        )
      )
      .catch((err: Error) => console.error('Failed to load satellites:', err));
  }, []);

  // Load route coordinates and waypoints when routeId changes
  useEffect(() => {
    if (!routeId) {
      return;
    }

    routesApi
      .getCoordinates(routeId)
      .then((coords) => setRouteCoordinates(coords))
      .catch((err) =>
        console.error('Failed to load route coordinates:', err)
      );

    routesApi
      .getWaypoints(routeId)
      .then((waypoints) => {
        setAvailableWaypoints(waypoints);
        setWaypointNames(
          waypoints.map((wp) => wp.name || '').filter((name) => name !== '')
        );
      })
      .catch((err) => console.error('Failed to load route waypoints:', err));

    // Cleanup: clear waypoints when effect unmounts or routeId changes
    return () => {
      setAvailableWaypoints([]);
      setWaypointNames([]);
    };
  }, [routeId]);

  // Load Ka transition POIs when routeId or missionId changes
  useEffect(() => {
    if (!routeId || !missionId) {
      return;
    }

    poisService
      .getPOIsByRoute(routeId, false)
      .then((pois) => {
        // Filter for Ka transition POIs that belong to THIS mission AND route
        const kaPois = pois.filter(
          (poi) =>
            poi.category === 'mission-event' &&
            poi.icon === 'satellite' &&
            poi.name.toLowerCase().includes('ka transition') &&
            poi.mission_id === missionId &&
            poi.route_id === routeId
        );

        // Convert POIs to KaTransition format
        const transitions = kaPois
          .map((poi) => convertPoiToKaTransition(poi))
          .filter((t): t is KaTransition => t !== null);

        setKaTransitions(transitions);
      })
      .catch((err) =>
        console.error('Failed to load Ka transition POIs:', err)
      );

    // Cleanup: clear Ka transitions when effect unmounts or dependencies change
    return () => {
      setKaTransitions([]);
    };
  }, [routeId, missionId]);

  // Sync state when leg transports data changes
  useEffect(() => {
    setSatelliteConfig(initializeSatelliteConfig(legTransports));
    setAARConfig(initializeAARConfig(legTransports));
  }, [legTransports]);

  return {
    satelliteConfig,
    setSatelliteConfig,
    aarConfig,
    setAARConfig,
    routeCoordinates,
    availableWaypoints,
    waypointNames,
    availableSatellites,
    kaTransitions,
    hasUnsavedChanges,
    setHasUnsavedChanges,
  };
}
