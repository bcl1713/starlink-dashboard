import { useState, useEffect, useMemo } from 'react';
import type { SatelliteConfig } from '../../types/satellite';
import type { AARConfig } from '../../types/aar';
import type { KaTransition } from '../../types/timeline';
import type { Waypoint } from '../../services/routes';
import type { TransportConfig } from '../../types/mission';
import { routesApi } from '../../services/routes';
import {
  satelliteService,
  type SatelliteResponse,
} from '../../services/satellites';
import { poisService, type POI } from '../../services/pois';

interface UseLegDataProps {
  routeId?: string;
  missionId?: string;
  legId?: string;
  legTransports?: TransportConfig;
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
function initializeSatelliteConfig(
  legTransports?: TransportConfig
): SatelliteConfig {
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
    xband_transitions: legTransports.x_transitions || [],
    ka_outages: legTransports.ka_outages || [],
    ku_outages: legTransports.ku_overrides || [],
  };
}

/**
 * Initialize AAR config from leg transports data
 */
function initializeAARConfig(legTransports?: TransportConfig): AARConfig {
  if (!legTransports) {
    return { segments: [], manualTracks: [] };
  }
  return {
    segments: legTransports.aar_windows || [],
    manualTracks: legTransports.manual_aar_tracks || [],
  };
}

/**
 * Custom hook for managing leg data, including routes, satellites, and configurations
 */
export function useLegData({
  routeId,
  missionId,
  legId,
  legTransports,
}: UseLegDataProps): UseLegDataReturn {
  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>(
    []
  );
  const [availableWaypoints, setAvailableWaypoints] = useState<Waypoint[]>([]);
  const [waypointNames, setWaypointNames] = useState<string[]>([]);
  const [availableSatellites, setAvailableSatellites] = useState<string[]>([]);
  const [kaTransitions, setKaTransitions] = useState<KaTransition[]>([]);
  const configScope = `${missionId ?? ''}:${legId ?? ''}`;
  const [dirtyState, setDirtyState] = useState({
    scope: configScope,
    value: false,
  });
  const hasUnsavedChanges =
    dirtyState.scope === configScope && dirtyState.value;
  const setHasUnsavedChanges: React.Dispatch<React.SetStateAction<boolean>> = (
    value
  ) => {
    setDirtyState((current) => ({
      scope: configScope,
      value:
        typeof value === 'function'
          ? value(current.scope === configScope && current.value)
          : value,
    }));
  };

  // Confirmed props remain separate from a local draft for this mission/leg.
  // Changing availability may refresh props without replacing pending edits.
  const confirmedConfig = useMemo(
    () => ({
      scope: configScope,
      base: legTransports,
      satellite: initializeSatelliteConfig(legTransports),
      aar: initializeAARConfig(legTransports),
    }),
    [configScope, legTransports]
  );
  const [localConfig, setLocalConfig] = useState<typeof confirmedConfig | null>(
    null
  );
  const currentConfig = (candidate: typeof localConfig) =>
    candidate?.scope === configScope &&
    (candidate.base === legTransports || hasUnsavedChanges)
      ? candidate
      : confirmedConfig;
  const config = currentConfig(localConfig);
  const satelliteConfig = config.satellite;
  const aarConfig = config.aar;
  const setSatelliteConfig: React.Dispatch<
    React.SetStateAction<SatelliteConfig>
  > = (value) => {
    setLocalConfig((current) => {
      const base = currentConfig(current);
      return {
        ...base,
        satellite: typeof value === 'function' ? value(base.satellite) : value,
      };
    });
  };
  const setAARConfig: React.Dispatch<React.SetStateAction<AARConfig>> = (
    value
  ) => {
    setLocalConfig((current) => {
      const base = currentConfig(current);
      return {
        ...base,
        aar: typeof value === 'function' ? value(base.aar) : value,
      };
    });
  };

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
      .catch((err) => console.error('Failed to load route coordinates:', err));

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
            poi.transport_active !== false &&
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
      .catch((err) => console.error('Failed to load Ka transition POIs:', err));

    // Cleanup: clear Ka transitions when effect unmounts or dependencies change
    return () => {
      setKaTransitions([]);
    };
  }, [routeId, missionId]);

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
