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
import { isStatusStale } from './status-freshness';
import { useCurrentTime } from '@/hooks/useCurrentTime';
import {
  GEO_ANALYSIS_CAMERA_POSITION,
  ROUTE_OVERLAY_RADIUS,
} from './globe-render-radii';
import { CityLitGlobe } from './CityLitGlobe';
import { globePosition } from './globe-coordinates';
import { useSatellites } from '@/hooks/api/useSatellites';
import { projectConfiguredXBandSatellite3d } from './x-band-satellites-projection';
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
import {
  activeLinkFlowEmitters,
  routeFlowEmitters,
} from './overview-flow-consumers';
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
import { OverviewMapLegend } from './OverviewMapLegend';
import { OverviewMapStatus } from './OverviewMapStatus';
import { useOverviewLayout } from './useOverviewLayout';
import { OverviewMapControls } from './OverviewMapControls';
import { OverviewMapController } from './OverviewMapController';
import { useOverviewFollowPreference } from '@/hooks/useOverviewFollowPreference';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import type { OverviewCameraIntent } from './overview-camera-frame';
import type { OverviewLayoutMode } from './overview-responsive-layout';

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
}: {
  coordinate: GlobeCoordinate;
  position: [number, number, number] | null;
}) {
  return position ? (
    <StarMarker position={position} color="#72b7ff" size={0.15} />
  ) : (
    <StarMarker coordinate={coordinate} color="#72b7ff" size={0.15} />
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
  const followPreference = useOverviewFollowPreference();
  const [resetRevision, setResetRevision] = useState(0);
  const pageRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
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
  } = useRoutes();

  const routeId = activeRouteId(routes);

  const {
    data: activeRoute,
    isLoading: isLoadingRoute,
    error: routeError,
  } = useRoute(routeId ?? '');

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
  const {
    data: upcomingPoisResponse,
    isError: arrivalRefreshFailed,
    isLoading: isLoadingUpcomingPois,
  } = useOverviewUpcomingPois();
  const arrivalState = deriveArrivalPanel(
    upcomingPoisResponse,
    currentTime,
    arrivalRefreshFailed
  );
  const upcomingPoiView = useMemo(
    () => overviewPoiView(upcomingPoisResponse?.pois ?? []),
    [upcomingPoisResponse?.pois]
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
  } = useOverviewClockSettings();
  const {
    data: status,
    isLoading: isLoadingStatus,
    error: statusError,
  } = useStatus();
  const {
    data: overviewHistory,
    isLoading: isLoadingOverviewHistory,
    isError: isOverviewHistoryError,
  } = useOverviewHistory();
  const { data: overviewHistorySettings } = useOverviewHistorySettings();
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
  } = useSatellites();

  const {
    data: activeXLink,
    isLoading: isLoadingActiveXLink,
    error: activeXLinkError,
  } = useActiveXLink();
  const activeConfiguredXBandSatelliteId =
    projectActiveConfiguredXBandSatelliteId(activeXLink);
  const activeConfiguredXBandLink = activeConfiguredXBandSatelliteId
    ? projectConfiguredXBandActiveLink(
        status,
        satellites,
        activeConfiguredXBandSatelliteId
      )
    : null;
  const activeLinkFlow = useMemo(() => {
    const network = status?.network;
    return activeLinkFlowEmitters(
      network
        ? {
            latency_ms: network.latency_ms ?? undefined,
            throughput_down_mbps: network.throughput_down_mbps ?? undefined,
            throughput_up_mbps: network.throughput_up_mbps ?? undefined,
            packet_loss_percent: network.packet_loss_percent ?? undefined,
          }
        : undefined
    );
  }, [status?.network]);
  const activeXBandLineStyle = satcomLineStyle(activeXLink?.state);
  const configuredXBandSatellites =
    projectConfiguredXBandSatellite3d(satellites);
  const plannedSatelliteState = derivePlannedSatelliteState(
    activeXLink,
    isLoadingActiveXLink,
    Boolean(activeXLinkError)
  );

  const aircraftPosition = projectAircraftPosition(status ?? {});
  const aircraftScenePosition = projectAircraftScenePosition(status);
  const groundEntryPoint = projectGroundEntryPoint(status ?? {});

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
          currentTime={currentTime}
          isError={isOverviewClockSettingsError}
          isLoading={isLoadingOverviewClockSettings}
        />
      </div>
      <div
        ref={stageRef}
        className="overview-map-stage"
        data-flow={layout.flow}
      >
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
          <OverviewFullscreenControl />
          <div className="overview-map-overlays">
            <OverviewMapStatus messages={mapMessages} />
            <OverviewMapLegend
              collapsible={layout.mode !== 'desktop'}
              aircraft={Boolean(aircraftPosition)}
              route={hasRenderableRoute}
              history={aircraftHistoryPoints.length >= 2}
              groundEntryPoint={Boolean(groundEntryPoint)}
              plannedLink={Boolean(activeConfiguredXBandLink)}
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
                  new Date(currentTime)
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
            {activeConfiguredXBandLink && (
              <>
                <AnimatedFlowLine
                  points={activeConfiguredXBandLink.points}
                  forward={activeLinkFlow.forward}
                  reverse={activeLinkFlow.reverse}
                  outer={activeXBandLineStyle.outer}
                  glow={activeXBandLineStyle.glow}
                  core={activeXBandLineStyle.core}
                  depthWrite={false}
                />
              </>
            )}
            {configuredXBandSatellites.map((satellite) => (
              <ConfiguredXBandSatelliteMarker
                key={`${satellite.satelliteId}-${satellite.longitude}`}
                satelliteId={satellite.satelliteId}
                position={satellite.position}
                globeOccluder={globeOccluder}
              />
            ))}
            {aircraftHistoryPoints.length >= 2 && (
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
              />
            )}
          </Suspense>
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
        <OverviewMetricHistoryPanels
          status={status}
          statusError={Boolean(statusError)}
          history={overviewHistory}
          error={isOverviewHistoryError}
          selectedWindowSeconds={overviewHistorySettings?.window_seconds}
          nowMs={currentTime}
        />
      </div>
    </main>
  );
}
