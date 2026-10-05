import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from 'react';
import { Canvas } from '@react-three/fiber';
import { Html, Stars } from '@react-three/drei';
import * as THREE from 'three';
import './OverviewPage.css';
import './OverviewOverlayLayout.css';
import { useOverviewAdsbLayer } from '@/hooks/useOverviewAdsbLayer';
import { OverviewAdsbLayer } from './adsb/OverviewAdsbLayer';
import { OverviewAdsbDetails } from './adsb/OverviewAdsbDetails';
import { type GlobeCoordinate } from './globe-route';
import { activeRouteId } from './active-globe-route';
import { projectRouteArc } from './globe-route-projection';
import { useRoute, useRoutes } from '../hooks/api/useRoutes';
import { sunLightPosition } from './solar-position';
import { millisecondsUntilNextMinute } from './solar-clock';
import { useStatus } from '@/hooks/api/useStatus';
import {
  projectAircraftPosition,
  projectGroundEntryPoint,
} from './status-projection';
import { StarMarker } from './OverviewStarMarker';
import { OverviewMarkerDebug } from './OverviewMarkerDebug';
import {
  DEFAULT_CHEVRON_SETTINGS,
  type ChevronSettings,
} from './overview-chevron-settings';
import { isStatusStale } from './status-freshness';
import { useCurrentTime } from '@/hooks/useCurrentTime';
import {
  GEO_ANALYSIS_CAMERA_POSITION,
  ROUTE_OVERLAY_RADIUS,
} from './globe-render-radii';
import { CityLitGlobe } from './CityLitGlobe';
import { globePosition } from './globe-coordinates';
import { useSatellites } from '@/hooks/api/useSatellites';
import {
  projectConfiguredXBandSatellite3d,
  projectConfiguredXBandSatellites,
} from './x-band-satellites-projection';
import { useActiveXLink } from '@/hooks/api/useActiveXLink';
import { satcomLineStyle } from './satcom-link-style';
import {
  projectActiveConfiguredXBandSatelliteId,
  projectAircraftScenePosition,
  projectConfiguredXBandActiveLink,
} from './x-band-active-link-projection';
import { useOverviewHistory } from '@/hooks/api/useOverviewHistory';
import { projectAircraftHistory } from './overview-history-projection';
import { useOverviewHistorySettings } from '@/hooks/api/useOverviewHistorySettings';
import { AnimatedFlowLine } from './AnimatedFlowLine';
import { routeFlowEmitters } from './overview-flow-consumers';
import { useOverviewLinkSettings } from '@/hooks/api/useOverviewLinkSettings';
import { deriveOverviewLinkState } from './overview-link-state';
import { TRAFFIC_PATH_STYLE } from './overview-traffic-style';
import { useOverviewClockSettings } from '@/hooks/api/useOverviewClockSettings';
import { OverviewClockPanel } from './OverviewClockPanel';
import { OverviewFullscreenControl } from './OverviewFullscreenControl';
import { useOverviewUpcomingPois } from '@/hooks/api/useOverviewUpcomingPois';
import { overviewPoiView, urgencyColor } from './overview-upcoming-pois';
import { OverviewPoiMarker } from './OverviewPoiMarker';
import {
  layoutOverviewPoiLabels,
  type PoiLabelLayout,
} from './overview-poi-label-layout';
import { OverviewArrivalPanel } from './OverviewArrivalPanel';
import { deriveArrivalPanel } from './overview-arrival';
import { OverviewMetricHistoryPanels } from './OverviewMetricHistoryPanels';
import { derivePlannedSatelliteState } from './overview-planned-satellite';
import { OverviewPlannedSatelliteCard } from './OverviewPlannedSatelliteCard';
import { useOrbitalTraffic } from '@/hooks/useOrbitalTraffic';
import { OrbitalSprites } from './orbital/OrbitalSprites';
import { chooseTrafficPath } from './orbital/traffic-path';
import { sceneToEcefKm } from './orbital/coordinates';
import { OverviewMapLegend } from './OverviewMapLegend';
import { OverviewMapStatus } from './OverviewMapStatus';
import { useOverviewLayout } from './useOverviewLayout';
import { OverviewMapControls } from './OverviewMapControls';
import { OverviewMapController } from './OverviewMapController';
import { useOverviewFollowPreference } from '@/hooks/useOverviewFollowPreference';
import { useOverviewDisplayHost } from '@/hooks/useOverviewDisplayHost';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import type { OverviewCameraIntent } from './overview-camera-frame';
import type { OverviewLayoutMode } from './overview-responsive-layout';
import {
  useSimulationRun,
  useSimulationRunRoute,
} from '@/hooks/api/useSimulationRun';
import { useSimulationClock } from '@/hooks/useSimulationClock';
import { SimulationRunPanel } from './SimulationRunPanel';

const AIRCRAFT_HISTORY_LINE = {
  outer: {
    color: '#00d9ff',
    linewidth: 8,
    opacity: 0.08,
    blending: THREE.AdditiveBlending,
    maxWorldWidth: 0.035,
  },
  glow: {
    color: '#00f5ff',
    linewidth: 4,
    opacity: 0.32,
    blending: THREE.AdditiveBlending,
    maxWorldWidth: 0.02,
  },
  core: {
    color: '#d9ffff',
    linewidth: 1.15,
    opacity: 0.95,
    blending: THREE.NormalBlending,
    maxWorldWidth: 0.008,
  },
};

const atmosphereVertexShader = `
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    vNormal = normalize(normalMatrix * normal);

    vec4 modelViewPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -modelViewPosition.xyz;

    gl_Position = projectionMatrix * modelViewPosition;
  }
`;

const atmosphereFragmentShader = `
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    float viewAngle = max(
      dot(normalize(vNormal), normalize(vViewPosition)),
      0.0
    );

    float rim = pow(1.0 - viewAngle, 3.0);
    vec3 atmosphereColor = vec3(0.16, 0.55, 1.0);

    gl_FragColor = vec4(atmosphereColor * rim, rim * 0.22);
  }
`;

function AircraftMarker({
  coordinate,
  position,
  headingDegrees,
  chevronSettings,
}: {
  coordinate: GlobeCoordinate;
  position: [number, number, number] | null;
  headingDegrees?: number;
  chevronSettings: Readonly<ChevronSettings>;
}) {
  return position ? (
    <StarMarker
      position={position}
      color="#72b7ff"
      size={0.15}
      shape="chevron"
      headingDegrees={headingDegrees}
      chevronSettings={chevronSettings}
      renderOrder={1000}
    />
  ) : (
    <StarMarker
      coordinate={coordinate}
      color="#72b7ff"
      size={0.15}
      shape="chevron"
      headingDegrees={headingDegrees}
      chevronSettings={chevronSettings}
      renderOrder={1000}
    />
  );
}

function GroundEntryPointMarker({
  coordinate,
  globeOccluder,
}: {
  coordinate: GlobeCoordinate;
  globeOccluder: RefObject<THREE.Group>;
}) {
  return (
    <>
      <StarMarker coordinate={coordinate} color="#c084fc" size={0.13} />
      <Html
        occlude={[globeOccluder]}
        position={globePosition(
          coordinate.latitude,
          coordinate.longitude,
          ROUTE_OVERLAY_RADIUS
        )}
        zIndexRange={[0, 0]}
      >
        <span className="globe-marker-label">GEP</span>
      </Html>
    </>
  );
}

function ConfiguredXBandSatelliteMarker({
  satelliteId,
  position,
  globeOccluder,
}: {
  satelliteId: string;
  position: [number, number, number];
  globeOccluder: RefObject<THREE.Group>;
}) {
  return (
    <>
      <StarMarker position={position} color="#FF6B6B" size={0.13} />
      <Html occlude={[globeOccluder]} position={position} zIndexRange={[0, 0]}>
        <span className="globe-marker-label">{satelliteId}</span>
      </Html>
    </>
  );
}

function Atmosphere() {
  return (
    <mesh scale={1.025}>
      <sphereGeometry args={[2, 64, 64]} />
      <shaderMaterial
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        vertexShader={atmosphereVertexShader}
        fragmentShader={atmosphereFragmentShader}
      />
    </mesh>
  );
}

export function OverviewPage() {
  const markerDebug =
    new URLSearchParams(window.location.search).get('markerDebug') === '1';
  const [chevronSettings, setChevronSettings] = useState<
    Readonly<ChevronSettings>
  >(DEFAULT_CHEVRON_SETTINGS);
  const followPreference = useOverviewFollowPreference();
  const [resetRevision, setResetRevision] = useState(0);
  const pageRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [stageNode, setStageNode] = useState<HTMLDivElement | null>(null);
  const captureStage = useCallback((node: HTMLDivElement | null) => {
    stageRef.current = node;
    setStageNode(node);
  }, []);
  const adsb = useOverviewAdsbLayer();
  const [selectedAdsbHex, setSelectedAdsbHex] = useState<string | null>(null);
  const [visibleAdsbHexes, setVisibleAdsbHexes] = useState<readonly string[]>(
    []
  );
  const adsbReturnFocus = useRef<HTMLElement | null>(null);
  const selectedAdsbContact =
    adsb.contacts.find((c) => c.hex === selectedAdsbHex) ?? null;
  if (selectedAdsbHex && !selectedAdsbContact) setSelectedAdsbHex(null);
  const selectAdsb = useCallback((hex: string) => {
    adsbReturnFocus.current =
      document.activeElement instanceof HTMLElement &&
      document.activeElement !== document.body
        ? document.activeElement
        : stageRef.current;
    setSelectedAdsbHex(hex);
  }, []);
  const updateVisibleAdsb = useCallback((hexes: readonly string[]) => {
    setVisibleAdsbHexes((old) =>
      old.join('|') === hexes.join('|') ? old : hexes
    );
  }, []);
  const [cameraIntent, setCameraIntent] = useState<OverviewCameraIntent>(
    followPreference ? 'follow' : 'automatic'
  );
  const [previousFollowPreference, setPreviousFollowPreference] =
    useState(followPreference);
  if (previousFollowPreference !== followPreference) {
    setPreviousFollowPreference(followPreference);
    setCameraIntent(followPreference ? 'follow' : 'manual');
  }
  const [exploration, setExploration] = useState<{
    mode: OverviewLayoutMode;
    active: boolean;
  }>({ mode: 'desktop', active: false });
  const [poseRevision, setPoseRevision] = useState(0);
  const reducedMotion = usePrefersReducedMotion();
  const onManual = useCallback(() => setCameraIntent('manual'), []);
  const onCameraSettled = useCallback(
    () => setPoseRevision((value) => value + 1),
    []
  );
  const [solarTime, setSolarTime] = useState(() => new Date());

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;

    const updateSolarTime = () => {
      const now = new Date();

      setSolarTime(now);
      timeoutId = setTimeout(updateSolarTime, millisecondsUntilNextMinute(now));
    };

    const now = new Date();

    timeoutId = setTimeout(updateSolarTime, millisecondsUntilNextMinute(now));

    return () => {
      clearTimeout(timeoutId);
    };
  }, []);

  const sunPosition = useMemo(
    () => sunLightPosition(solarTime, 10),
    [solarTime]
  );

  const globeOccluder = useRef<THREE.Group>(new THREE.Group());

  const {
    data: routes = [],
    isLoading: isLoadingRoutes,
    error: routesError,
  } = useRoutes(true);

  const routeId = activeRouteId(routes);
  const { data: simulationRun, isError: simulationRefreshFailed } =
    useSimulationRun();
  const pacedRunning = simulationRun?.state === 'running';
  const { data: replayGeometry } = useSimulationRunRoute(simulationRun);

  const {
    data: ordinaryRoute,
    isLoading: isLoadingRoute,
    error: routeError,
  } = useRoute(routeId ?? '', true);
  const activeRoute =
    replayGeometry &&
    simulationRun &&
    replayGeometry.runtime_id === simulationRun.runtime_id &&
    replayGeometry.run_id === simulationRun.run?.run_id &&
    ['running', 'completed'].includes(simulationRun.state)
      ? replayGeometry.route
      : ordinaryRoute;

  const routePoints = useMemo(
    () => projectRouteArc(activeRoute?.points ?? [], ROUTE_OVERLAY_RADIUS, 8),
    [activeRoute?.points]
  );
  const routeFlow = useMemo(() => routeFlowEmitters(), []);

  const isLoading = isLoadingRoutes || (routeId !== null && isLoadingRoute);
  const hasRenderableRoute = routePoints.length >= 2;
  const routeStatus =
    routesError || routeError
      ? 'Unable to load the active route.'
      : isLoading
        ? 'Loading active route...'
        : routeId === null
          ? 'No active route.'
          : !hasRenderableRoute
            ? 'The active route has no renderable points.'
            : null;

  const currentTime = useCurrentTime(1_000);
  const simulationClock = useSimulationClock(
    simulationRun,
    currentTime,
    simulationRefreshFailed
  );
  const missionNow = simulationClock.missionNowMs;
  const {
    data: upcomingPoisResponse,
    isError: arrivalRefreshFailed,
    isLoading: isLoadingUpcomingPois,
  } = useOverviewUpcomingPois(pacedRunning);
  const arrivalState = deriveArrivalPanel(
    upcomingPoisResponse,
    currentTime,
    arrivalRefreshFailed,
    simulationRun?.state === 'completed' &&
      upcomingPoisResponse?.mission_time &&
      upcomingPoisResponse.mission_time.run_id === simulationRun.run?.run_id
      ? Date.parse(upcomingPoisResponse.mission_time.simulation_time)
      : missionNow
  );
  const upcomingPoiView = useMemo(
    () =>
      overviewPoiView(
        upcomingPoisResponse?.pois ?? [],
        pacedRunning ? missionNow : undefined
      ),
    [upcomingPoisResponse?.pois, pacedRunning, missionNow]
  );
  const [upcomingPoiLabelLayout, setUpcomingPoiLabelLayout] =
    useState<PoiLabelLayout>({
      offsets: {},
      fallback: null,
    });
  const {
    data: overviewClockSettings,
    isError: isOverviewClockSettingsError,
    isLoading: isLoadingOverviewClockSettings,
  } = useOverviewClockSettings(true);
  const {
    data: status,
    isLoading: isLoadingStatus,
    error: statusError,
    failureCount: statusFailureCount,
  } = useStatus();
  // Refetch retries keep cached data and leave error null until exhausted.
  // Link activity stops on the first failed attempt and resumes on success.
  const statusRequestFailed = Boolean(statusError) || statusFailureCount > 0;
  const { data: overviewLinkSettings } = useOverviewLinkSettings(true);
  const {
    data: overviewHistory,
    isLoading: isLoadingOverviewHistory,
    isError: isOverviewHistoryError,
  } = useOverviewHistory();
  const { data: overviewHistorySettings } = useOverviewHistorySettings(true);
  const aircraftHistoryPoints = useMemo(
    () =>
      projectAircraftHistory(
        overviewHistory?.series ?? {},
        ROUTE_OVERLAY_RADIUS + 0.00001
      ),
    [overviewHistory?.series]
  );
  const {
    data: satellites,
    isLoading: isLoadingSatellites,
    error: satellitesError,
  } = useSatellites(true);

  const {
    data: activeXLink,
    isLoading: isLoadingActiveXLink,
    error: activeXLinkError,
  } = useActiveXLink();
  const showAircraftHistory =
    (overviewLinkSettings?.aircraft_history_enabled ?? true) &&
    aircraftHistoryPoints.length >= 2;

  const aircraftPosition = projectAircraftPosition(status ?? {});
  const aircraftScenePosition = projectAircraftScenePosition(status);
  const groundEntryPoint = projectGroundEntryPoint(status ?? {});
  const aircraftLatitude = aircraftScenePosition?.latitude;
  const aircraftLongitude = aircraftScenePosition?.longitude;
  const aircraftAltitudeFeet = aircraftScenePosition?.altitudeFeet;
  const configuredXBandSatellites =
    projectConfiguredXBandSatellite3d(satellites);
  const activeConfiguredXBandSatelliteId =
    projectActiveConfiguredXBandSatelliteId(activeXLink);
  const activeSatelliteLongitude = projectConfiguredXBandSatellites(
    satellites
  ).find(
    (satellite) => satellite.satelliteId === activeConfiguredXBandSatelliteId
  )?.longitude;
  const activeConfiguredXBandLink = useMemo(() => {
    if (
      !activeConfiguredXBandSatelliteId ||
      activeSatelliteLongitude === undefined
    )
      return null;
    return projectConfiguredXBandActiveLink(
      {
        position: {
          latitude: aircraftLatitude,
          longitude: aircraftLongitude,
          altitude: aircraftAltitudeFeet,
        },
      },
      [
        {
          satellite_id: activeConfiguredXBandSatelliteId,
          transport: 'X',
          longitude: activeSatelliteLongitude,
        },
      ],
      activeConfiguredXBandSatelliteId
    );
  }, [
    activeConfiguredXBandSatelliteId,
    activeSatelliteLongitude,
    aircraftLatitude,
    aircraftLongitude,
    aircraftAltitudeFeet,
  ]);
  const activeXBandLineStyle = satcomLineStyle(activeXLink?.state);
  const plannedSatelliteState = derivePlannedSatelliteState(
    activeXLink,
    isLoadingActiveXLink,
    Boolean(activeXLinkError)
  );

  const trafficGeometryEligible = Boolean(
    overviewLinkSettings?.starshield_link_enabled &&
      aircraftScenePosition &&
      groundEntryPoint &&
      status &&
      !statusRequestFailed &&
      !isStatusStale(status.timestamp, currentTime)
  );
  const popLatitude = groundEntryPoint?.latitude;
  const popLongitude = groundEntryPoint?.longitude;
  const orbitalEndpoints = useMemo(
    () => ({
      aircraft:
        aircraftLatitude === undefined ||
        aircraftLongitude === undefined ||
        aircraftAltitudeFeet === undefined
          ? null
          : sceneToEcefKm(
              projectAircraftScenePosition({
                position: {
                  latitude: aircraftLatitude,
                  longitude: aircraftLongitude,
                  altitude: aircraftAltitudeFeet,
                },
              })!.position
            ),
      pop:
        popLatitude === undefined || popLongitude === undefined
          ? null
          : sceneToEcefKm(globePosition(popLatitude, popLongitude, 2)),
    }),
    [
      aircraftLatitude,
      aircraftLongitude,
      aircraftAltitudeFeet,
      popLatitude,
      popLongitude,
    ]
  );
  const orbital = useOrbitalTraffic({
    settings: overviewLinkSettings,
    endpoints: orbitalEndpoints,
  });
  const { current: orbitalSnapshot, route: orbitalRoute } = orbital;
  const showSprites = Boolean(
    overviewLinkSettings?.orbital_traffic_enabled &&
      overviewLinkSettings.starshield_link_enabled &&
      orbital.spritesReady &&
      orbital.current?.valid.some(Boolean)
  );
  const chosenTraffic = useMemo(() => {
    if (
      !trafficGeometryEligible ||
      popLatitude === undefined ||
      popLongitude === undefined
    )
      return { points: [], particleKey: `pop:${popLatitude}:${popLongitude}` };
    // Reconstruct from scalar endpoints so new polled status objects and metric
    // changes retain the same prepared arc and renderer resources.
    return chooseTrafficPath(
      showSprites ? orbitalRoute : null,
      showSprites ? orbitalSnapshot : null,
      projectAircraftScenePosition({
        position: {
          latitude: aircraftLatitude,
          longitude: aircraftLongitude,
          altitude: aircraftAltitudeFeet,
        },
      }),
      { latitude: popLatitude, longitude: popLongitude }
    );
  }, [
    trafficGeometryEligible,
    showSprites,
    orbitalRoute,
    orbitalSnapshot,
    aircraftLatitude,
    aircraftLongitude,
    aircraftAltitudeFeet,
    popLatitude,
    popLongitude,
  ]);
  const trafficPoints = chosenTraffic.points;
  const linkState = deriveOverviewLinkState({
    settings: overviewLinkSettings,
    status,
    nowMs: currentTime,
    statusRequestFailed,
    hasTrafficGeometry: trafficPoints.length >= 2,
    hasXBandGeometry: Boolean(activeConfiguredXBandLink),
    selectionState: activeXLink?.state ?? null,
    selectionRequestFailed: Boolean(activeXLinkError || satellitesError),
  });
  const starshieldCanAnimate =
    linkState.starshieldVisible &&
    (linkState.starshieldFlow.forward.enabled ||
      linkState.starshieldFlow.reverse.enabled);
  const xBandCanAnimate =
    linkState.xBandVisible &&
    (linkState.xBandFlow.forward.enabled ||
      linkState.xBandFlow.reverse.enabled);
  const statusTimestamp = status?.timestamp;
  const canAnimateStarshield = useCallback(
    () =>
      starshieldCanAnimate &&
      typeof statusTimestamp === 'string' &&
      !isStatusStale(statusTimestamp, Date.now()),
    [starshieldCanAnimate, statusTimestamp]
  );
  const canAnimateXBand = useCallback(
    () =>
      xBandCanAnimate &&
      typeof statusTimestamp === 'string' &&
      !isStatusStale(statusTimestamp, Date.now()),
    [xBandCanAnimate, statusTimestamp]
  );

  const mapMessages = [
    routeStatus,
    statusError
      ? 'Status refresh unavailable'
      : isLoadingStatus
        ? 'Loading status…'
        : !status
          ? 'Status unavailable'
          : isStatusStale(status.timestamp, currentTime)
            ? 'Status stale · last known'
            : null,
    !aircraftPosition && !isLoadingStatus ? 'Position unavailable' : null,
    !groundEntryPoint && !isLoadingStatus ? 'GEP unavailable' : null,
    isOverviewHistoryError
      ? 'Track history unavailable'
      : isLoadingOverviewHistory
        ? 'Loading track history…'
        : null,
    satellitesError
      ? 'Satellite configuration unavailable'
      : isLoadingSatellites
        ? 'Loading satellite configuration…'
        : null,
    activeXLinkError ? 'Satellite selection unavailable' : null,
    activeConfiguredXBandSatelliteId && !activeConfiguredXBandLink
      ? 'Planned link unavailable'
      : null,
    activeXLink?.state === 'warning'
      ? activeXLinkError
        ? 'Last-known planned link warning'
        : 'Planned link warning'
      : null,
  ].filter((message): message is string => message !== null);

  const contentKey = JSON.stringify([
    arrivalState.sections.map((section) => [
      section.label,
      section.name,
      Boolean(section.timing),
      section.unavailable,
    ]),
    arrivalState.message,
    arrivalState.exception,
    plannedSatelliteState,
    mapMessages,
  ]);
  const contentReady =
    !isLoading &&
    !isLoadingStatus &&
    !isLoadingOverviewClockSettings &&
    !isLoadingOverviewHistory &&
    !isLoadingSatellites &&
    !isLoadingActiveXLink &&
    !isLoadingUpcomingPois;
  const layout = useOverviewLayout(pageRef, stageRef, contentKey, contentReady);
  const exploring = exploration.mode === layout.mode && exploration.active;
  if (exploration.mode !== layout.mode) {
    setExploration({ mode: layout.mode, active: false });
  }
  const onExploreChange = useCallback(
    (active: boolean) => {
      setExploration({ mode: layout.mode, active });
      if (active) setCameraIntent('manual');
    },
    [layout.mode]
  );
  const onReset = useCallback(() => {
    setCameraIntent(followPreference ? 'follow' : 'automatic');
    setResetRevision((value) => value + 1);
    setExploration({ mode: layout.mode, active: false });
  }, [layout.mode, followPreference]);
  const displayHost = useOverviewDisplayHost(onReset);
  const followUnavailable = statusError
    ? 'Status refresh unavailable'
    : !aircraftPosition || !status
      ? 'Aircraft position unavailable'
      : isStatusStale(status.timestamp, currentTime)
        ? 'Aircraft position stale'
        : null;
  useEffect(() => {
    const page = pageRef.current;
    const rail = pageRef.current?.querySelector<HTMLElement>(
      '.overview-metrics-overlays'
    );
    if (!page || !rail || layout.mode !== 'landscape' || exploring) return;
    const wheel = (event: WheelEvent) => {
      if (event.target instanceof Node && rail.contains(event.target)) return;
      if (
        event.target instanceof Element &&
        event.target.closest('.overview-marker-debug')
      )
        return;
      if (event.ctrlKey || event.metaKey || !event.deltaY) return;
      const delta =
        event.deltaY *
        (event.deltaMode === 1
          ? 16
          : event.deltaMode === 2
            ? rail.clientHeight
            : 1);
      const next = Math.max(
        0,
        Math.min(rail.scrollHeight - rail.clientHeight, rail.scrollTop + delta)
      );
      if (next !== rail.scrollTop) {
        event.preventDefault();
        rail.scrollTop = next;
      }
    };
    page.addEventListener('wheel', wheel, { passive: false });
    return () => page.removeEventListener('wheel', wheel);
  }, [layout.mode, exploring]);
  useEffect(() => {
    let attempts = 0;
    let frame = 0;
    const measure = () => {
      const labels = upcomingPoiView.markers.flatMap((poi) => {
        const element = document.querySelector<HTMLElement>(
          `[data-poi-label="${poi.poi_id}"]`
        );
        if (!element) return [];

        const bounds = element.getBoundingClientRect();
        if (bounds.width === 0 || bounds.height === 0) return [];
        const [offsetX, offsetY] = (element.dataset.poiLabelOffset ?? '0,0')
          .split(',')
          .map(Number);
        return [
          {
            id: poi.poi_id,
            bounds: {
              x: bounds.x - offsetX,
              y: bounds.y - offsetY,
              width: bounds.width,
              height: bounds.height,
            },
          },
        ];
      });

      if (labels.length < upcomingPoiView.markers.length && attempts < 20) {
        attempts += 1;
        frame = window.requestAnimationFrame(measure);
        return;
      }

      const stageBounds = stageRef.current
        ?.querySelector('.overview-globe')
        ?.getBoundingClientRect();
      if (!stageBounds) return;
      const reserved = [
        ...(stageRef.current?.querySelectorAll<HTMLElement>(
          '.overview-planned-satellite, .overview-arrival, .globe-legend, .overview-fullscreen-control, .overview-map-status, .overview-map-controls'
        ) ?? []),
      ].map((node) => {
        const bounds = node.getBoundingClientRect();
        return {
          x: bounds.x - stageBounds.x,
          y: bounds.y - stageBounds.y,
          width: bounds.width,
          height: bounds.height,
        };
      });
      const nextLayout = layoutOverviewPoiLabels(
        labels.map((label) => ({
          ...label,
          bounds: {
            ...label.bounds,
            x: label.bounds.x - stageBounds.x,
            y: label.bounds.y - stageBounds.y,
          },
        })),
        { width: stageBounds.width, height: stageBounds.height },
        reserved
      );
      setUpcomingPoiLabelLayout((currentLayout) =>
        JSON.stringify(currentLayout) === JSON.stringify(nextLayout)
          ? currentLayout
          : nextLayout
      );
    };
    frame = window.requestAnimationFrame(measure);

    return () => window.cancelAnimationFrame(frame);
  }, [
    upcomingPoiLabelLayout,
    upcomingPoiView.markers,
    layout.revision,
    poseRevision,
  ]);
  return (
    <main
      ref={pageRef}
      className="overview-page"
      data-layout={layout.mode}
      data-map-exploring={exploring}
    >
      <div className="overview-top-overlays">
        <OverviewClockPanel
          clocks={overviewClockSettings?.clocks}
          currentTime={missionNow}
          simulated={pacedRunning}
          isError={isOverviewClockSettingsError}
          isLoading={isLoadingOverviewClockSettings}
        />
      </div>
      <div
        ref={captureStage}
        tabIndex={-1}
        className="overview-map-stage"
        data-flow={layout.flow}
        data-adsb-details-open={selectedAdsbContact !== null}
      >
        {markerDebug && (
          <OverviewMarkerDebug
            settings={chevronSettings}
            onChange={setChevronSettings}
          />
        )}
        <div className="overview-right-overlays">
          <div className="overview-satellite-overlays">
            <OverviewPlannedSatelliteCard state={plannedSatelliteState} />
          </div>
          <OverviewMapControls
            exploring={exploring}
            intent={cameraIntent}
            followUnavailable={followUnavailable}
            onExploreChange={onExploreChange}
            onReset={onReset}
          />
          <div className="overview-display-controls">
            {displayHost.label && (
              <span
                className="overview-display-label"
                aria-label="Overview display identity"
              >
                {displayHost.label}
              </span>
            )}
            <OverviewFullscreenControl />
          </div>
          <div className="overview-map-overlays">
            <OverviewMapStatus messages={mapMessages} />
            <OverviewMapLegend
              collapsible={layout.mode !== 'desktop'}
              aircraft={Boolean(aircraftPosition)}
              route={hasRenderableRoute}
              history={showAircraftHistory}
              groundEntryPoint={Boolean(groundEntryPoint)}
              satellites={showSprites}
              adsb={adsb.contacts.length > 0}
              trafficPath={linkState.starshieldVisible}
              plannedLink={linkState.xBandVisible}
              linkState={activeXLink?.state ?? null}
            />
          </div>
        </div>
        <div className="overview-arrival-overlays">
          <OverviewArrivalPanel state={arrivalState} />
          <ul className="overview-visually-hidden" aria-label="Map POIs">
            {upcomingPoiView.markers.map((poi) => (
              <li key={poi.poi_id}>{poi.name}</li>
            ))}
          </ul>
        </div>
        <ul
          className="overview-visually-hidden"
          aria-label="Configured map satellites"
        >
          {configuredXBandSatellites.map((satellite) => (
            <li key={satellite.satelliteId}>{satellite.satelliteId}</li>
          ))}
        </ul>
        <ul
          className="adsb-keyboard-contacts"
          aria-label="Visible ADS-B aircraft"
        >
          {adsb.contacts
            .filter((c) => visibleAdsbHexes.includes(c.hex))
            .map((c) => (
              <li key={c.hex}>
                <button
                  type="button"
                  aria-label={`Details for ${c.hex}`}
                  onClick={() => selectAdsb(c.hex)}
                >
                  {c.label} · {c.hex}
                  {c.freshness === 'stale' ? ' · ◷ Stale' : ''}
                </button>
              </li>
            ))}
        </ul>
        <OverviewAdsbDetails
          contact={selectedAdsbContact}
          onClose={() => setSelectedAdsbHex(null)}
          returnFocusRef={adsbReturnFocus}
          portalContainer={stageNode}
        />
        <Canvas
          className="overview-globe"
          camera={{ position: GEO_ANALYSIS_CAMERA_POSITION, fov: 45 }}
        >
          <color attach="background" args={['#030307']} />
          <ambientLight intensity={0.5} />
          <directionalLight position={sunPosition} intensity={5} />
          <Stars
            radius={50}
            depth={0}
            count={1500}
            factor={3}
            saturation={0}
            fade
            speed={reducedMotion ? 0 : 1.1}
          />
          <Stars
            radius={50}
            depth={0}
            count={1500}
            factor={3}
            saturation={0}
            fade
            speed={reducedMotion ? 0 : 0.75}
          />
          <Stars
            radius={50}
            depth={0}
            count={1500}
            factor={3}
            saturation={0}
            fade
            speed={reducedMotion ? 0 : 0.1}
          />
          <Suspense fallback={null}>
            <group ref={globeOccluder}>
              <CityLitGlobe sunPosition={sunPosition} />
            </group>
            <Atmosphere />
            {hasRenderableRoute && (
              <AnimatedFlowLine
                points={routePoints}
                forward={routeFlow.forward}
                reverse={routeFlow.reverse}
                depthWrite={false}
              />
            )}
            {upcomingPoiView.markers.map((poi) => (
              <OverviewPoiMarker
                key={poi.poi_id}
                poi={poi}
                color={urgencyColor(
                  poi.estimated_arrival_time,
                  new Date(missionNow)
                )}
                globeOccluder={globeOccluder}
                labelOffset={upcomingPoiLabelLayout.offsets[poi.poi_id]}
                hideLabel={Boolean(
                  upcomingPoiLabelLayout.fallback &&
                    poi.poi_id !== upcomingPoiLabelLayout.fallback.anchorId
                )}
                fallbackLabel={
                  upcomingPoiLabelLayout.fallback?.anchorId === poi.poi_id
                    ? `+${upcomingPoiLabelLayout.fallback.hiddenIds.length} POIs`
                    : undefined
                }
              />
            ))}
            {groundEntryPoint && (
              <GroundEntryPointMarker
                coordinate={groundEntryPoint}
                globeOccluder={globeOccluder}
              />
            )}
            {showSprites && orbital.current && (
              <OrbitalSprites
                current={orbital.current}
                previous={orbital.previous}
                generation={orbital.current.generation}
                reducedMotion={reducedMotion}
              />
            )}
            {linkState.starshieldVisible && (
              <AnimatedFlowLine
                points={trafficPoints}
                forward={linkState.starshieldFlow.forward}
                reverse={linkState.starshieldFlow.reverse}
                outer={TRAFFIC_PATH_STYLE.outer}
                glow={TRAFFIC_PATH_STYLE.glow}
                core={TRAFFIC_PATH_STYLE.core}
                canAnimate={canAnimateStarshield}
                particleKey={chosenTraffic.particleKey}
                depthWrite={false}
              />
            )}
            {linkState.xBandVisible && activeConfiguredXBandLink && (
              <AnimatedFlowLine
                points={activeConfiguredXBandLink.points}
                forward={linkState.xBandFlow.forward}
                reverse={linkState.xBandFlow.reverse}
                outer={activeXBandLineStyle.outer}
                glow={activeXBandLineStyle.glow}
                core={activeXBandLineStyle.core}
                canAnimate={canAnimateXBand}
                particleKey={`x-band:${activeConfiguredXBandSatelliteId}:${activeSatelliteLongitude}`}
                depthWrite={false}
              />
            )}
            {configuredXBandSatellites.map((satellite) => (
              <ConfiguredXBandSatelliteMarker
                key={`${satellite.satelliteId}-${satellite.longitude}`}
                satelliteId={satellite.satelliteId}
                position={satellite.position}
                globeOccluder={globeOccluder}
              />
            ))}
            {showAircraftHistory && (
              <AnimatedFlowLine
                points={aircraftHistoryPoints}
                depthWrite={false}
                outer={AIRCRAFT_HISTORY_LINE.outer}
                glow={AIRCRAFT_HISTORY_LINE.glow}
                core={AIRCRAFT_HISTORY_LINE.core}
              />
            )}
            {aircraftPosition && (
              <AircraftMarker
                coordinate={aircraftPosition}
                position={aircraftScenePosition?.position ?? null}
                headingDegrees={status?.position?.heading}
                chevronSettings={chevronSettings}
              />
            )}
          </Suspense>
          {adsb.contacts.length > 0 && (
            <OverviewAdsbLayer
              contacts={adsb.contacts}
              chevronSettings={chevronSettings}
              globeOccluder={globeOccluder}
              onSelect={selectAdsb}
              onVisibleHexesChange={updateVisibleAdsb}
            />
          )}
          <OverviewMapController
            mode={layout.mode}
            safeRect={layout.safeRect}
            exploring={exploring}
            intent={cameraIntent}
            aircraft={aircraftPosition}
            followAvailable={!followUnavailable}
            route={routePoints}
            initialReady={contentReady}
            resetRevision={resetRevision}
            reducedMotion={reducedMotion}
            onManual={onManual}
            onCameraSettled={onCameraSettled}
          />
        </Canvas>
      </div>
      <div className="overview-metrics-overlays">
        <SimulationRunPanel
          status={simulationRun}
          stale={simulationClock.stale}
          compact
        />
        {!pacedRunning && (
          <OverviewMetricHistoryPanels
            status={status}
            statusError={Boolean(statusError)}
            history={overviewHistory}
            error={isOverviewHistoryError}
            selectedWindowSeconds={overviewHistorySettings?.window_seconds}
            nowMs={currentTime}
          />
        )}
      </div>
    </main>
  );
}
