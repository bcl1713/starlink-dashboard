import {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from 'react';
import { Canvas } from '@react-three/fiber';
import { Html, OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';
import './OverviewPage.css';
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
import { OverviewMetricsPanel } from './OverviewMetricsPanel';
import {
  GEO_ANALYSIS_CAMERA_POSITION,
  GEO_ANALYSIS_MAX_DISTANCE,
  ROUTE_OVERLAY_RADIUS,
} from './globe-render-radii';
import { CityLitGlobe } from './CityLitGlobe';
import { globePosition } from './globe-coordinates';
import { useSatellites } from '@/hooks/api/useSatellites';
import { projectConfiguredXBandSatellite3d } from './x-band-satellites-projection';
import { useActiveXLink } from '@/hooks/api/useActiveXLink';
import { satcomLineStyle } from './satcom-link-style';
import {
  calculateConfiguredXBandLookAngles,
  projectActiveConfiguredXBandSatelliteId,
  projectAircraftScenePosition,
  projectConfiguredXBandActiveLink,
} from './x-band-active-link-projection';
import { useOverviewHistory } from '@/hooks/api/useOverviewHistory';
import { projectAircraftHistory } from './overview-history-projection';
import { overviewHistoryState } from './overview-history-state';
import { useOverviewHistorySettings } from '@/hooks/api/useOverviewHistorySettings';
import { useUpdateOverviewHistorySettings } from '@/hooks/api/useUpdateOverviewHistorySettings';
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
import { UpcomingPoisPanel } from './UpcomingPoisPanel';
const HISTORY_WINDOW_OPTIONS = [300, 900, 1800, 3600];

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
  const { data: upcomingPoisResponse } = useOverviewUpcomingPois();
  const upcomingPoiState = upcomingPoisResponse?.state ?? 'unavailable';
  const upcomingPoiView = useMemo(
    () =>
      overviewPoiView(upcomingPoisResponse?.pois ?? [], new Date(currentTime)),
    [currentTime, upcomingPoisResponse?.pois]
  );
  const [upcomingPoiLabelLayout, setUpcomingPoiLabelLayout] =
    useState<PoiLabelLayout>({
      offsets: {},
      fallback: null,
    });
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

      const nextLayout = layoutOverviewPoiLabels(labels, {
        width: window.innerWidth,
        height: window.innerHeight,
      });
      setUpcomingPoiLabelLayout((currentLayout) =>
        JSON.stringify(currentLayout) === JSON.stringify(nextLayout)
          ? currentLayout
          : nextLayout
      );
    };
    frame = window.requestAnimationFrame(measure);

    return () => window.cancelAnimationFrame(frame);
  }, [upcomingPoiLabelLayout, upcomingPoiView.markers]);
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
  const {
    data: overviewHistorySettings,
    isError: isOverviewHistorySettingsError,
  } = useOverviewHistorySettings();
  const {
    mutate: updateOverviewHistorySettings,
    isPending: isUpdatingOverviewHistorySettings,
  } = useUpdateOverviewHistorySettings();
  const overviewHistoryWindowValue = overviewHistorySettings
    ? String(overviewHistorySettings.window_seconds)
    : '';
  const hasCustomOverviewHistoryWindow =
    overviewHistorySettings !== undefined &&
    !HISTORY_WINDOW_OPTIONS.includes(overviewHistorySettings.window_seconds);
  const aircraftHistoryPoints = useMemo(
    () =>
      projectAircraftHistory(
        overviewHistory?.series ?? {},
        ROUTE_OVERLAY_RADIUS + 0.00001
      ),
    [overviewHistory?.series]
  );
  const aircraftHistoryStatus = overviewHistoryState({
    isLoading: isLoadingOverviewHistory,
    isError: isOverviewHistoryError,
    pointCount: aircraftHistoryPoints.length,
  });
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
  const activeLinkFlow = useMemo(
    () => activeLinkFlowEmitters(status?.network),
    [status?.network]
  );
  const activeXBandLineStyle = satcomLineStyle(activeXLink?.state);
  const activeConfiguredXBandLookAngles = activeConfiguredXBandLink
    ? calculateConfiguredXBandLookAngles(activeConfiguredXBandLink)
    : null;
  const activeConfiguredXBandGeometryState = activeConfiguredXBandLookAngles
    ? `Configured GEO estimate: azimuth ${activeConfiguredXBandLookAngles.azimuthDegrees.toFixed(1)}°, elevation ${activeConfiguredXBandLookAngles.elevationDegrees.toFixed(1)}°`
    : activeConfiguredXBandSatelliteId
      ? 'Configured GEO geometry unavailable'
      : 'No active configured X-band link';
  const activeConfiguredXBandLinkState = activeXLinkError
    ? 'Active X-band link unavailable'
    : isLoadingActiveXLink
      ? 'Loading active X-band link...'
      : activeConfiguredXBandSatelliteId
        ? `Selected configured satellite ${activeConfiguredXBandSatelliteId}`
        : 'No active configured X-band link';

  const configuredXBandSatellites =
    projectConfiguredXBandSatellite3d(satellites);

  const configuredXBandSatelliteState = satellitesError
    ? 'Satellite configuration unavailable'
    : isLoadingSatellites
      ? 'Loading satellite configuration...'
      : configuredXBandSatellites.length === 0
        ? 'No valid configured satellites'
        : configuredXBandSatellites.length === 1
          ? '1 configured satellite'
          : configuredXBandSatellites.length + ' configured satellites';

  const aircraftPosition = projectAircraftPosition(status ?? {});
  const aircraftScenePosition = projectAircraftScenePosition(status);
  const groundEntryPoint = projectGroundEntryPoint(status ?? {});

  const telemetryState = statusError
    ? 'Telemetry error'
    : isLoadingStatus
      ? 'Loading telemetry…'
      : !status
        ? 'Telemetry unavailable'
        : isStatusStale(status.timestamp, currentTime)
          ? 'Telemetry stale'
          : !aircraftPosition
            ? 'Position unavailable'
            : 'Live telemetry';

  return (
    <main className="overview-page">
      <OverviewFullscreenControl />
      <aside
        className="globe-legend"
        aria-label="Globe legend"
        role={routesError || routeError ? 'alert' : undefined}
      >
        <p className="globe-legend__title">Globe</p>
        <ul className="globe-legend__items">
          {routeStatus ? (
            <li>
              <span aria-hidden="true" />
              <span>Route</span>
              <strong>{routeStatus}</strong>
            </li>
          ) : (
            <>
              <li>
                <span aria-hidden="true" />
                <span>Generated POIs</span>
                <strong>Colour indicates estimated arrival urgency</strong>
              </li>
              <li>
                <span className="globe-legend__route" aria-hidden="true" />
                <span>Path</span>
                <strong>{activeRoute?.name}</strong>
              </li>
            </>
          )}
          <li>
            <span
              className="globe-legend__marker globe-legend__marker--aircraft"
              aria-hidden="true"
            />
            <span>Aircraft position</span>
            <strong>{telemetryState}</strong>
          </li>
          <li>
            <span
              className="globe-legend__route globe-legend__route--history"
              aria-hidden="true"
            />
            <span>Aircraft history</span>
            <strong>{aircraftHistoryStatus}</strong>
          </li>
          <li>
            <span aria-hidden="true" />
            <label htmlFor="aircraft-history-window">
              Aircraft history window
            </label>
            <select
              id="aircraft-history-window"
              aria-label="Aircraft history window"
              className="globe-legend__window"
              value={overviewHistoryWindowValue}
              disabled={
                !overviewHistorySettings || isUpdatingOverviewHistorySettings
              }
              onChange={(event) => {
                const windowSeconds = Number(event.target.value);
                if (Number.isInteger(windowSeconds) && windowSeconds > 0) {
                  updateOverviewHistorySettings(windowSeconds);
                }
              }}
            >
              {!overviewHistorySettings && (
                <option value="" disabled>
                  {isOverviewHistorySettingsError ? 'Unavailable' : 'Loading…'}
                </option>
              )}
              {hasCustomOverviewHistoryWindow && (
                <option value={overviewHistoryWindowValue}>
                  {overviewHistoryWindowValue} seconds
                </option>
              )}
              {HISTORY_WINDOW_OPTIONS.map((windowSeconds) => (
                <option key={windowSeconds} value={windowSeconds}>
                  {windowSeconds / 60} minutes
                </option>
              ))}
            </select>
          </li>
          <li>
            <span
              className="globe-legend__marker globe-legend__marker--ground-entry"
              aria-hidden="true"
            />
            <span>Ground entry point</span>
            <strong>
              {groundEntryPoint ? 'Current/last-known' : 'GEP unavailable'}
            </strong>
          </li>
          <li>
            <span aria-hidden="true" />
            <span>Configured X-band satellites</span>
            <strong>{configuredXBandSatelliteState}</strong>
          </li>
          <li>
            <span aria-hidden="true" />
            <span>Active configured X-band link</span>
            <strong>{activeConfiguredXBandLinkState}</strong>
          </li>
          <li>
            <span aria-hidden="true" />
            <span>Configured GEO analysis</span>
            <strong>{activeConfiguredXBandGeometryState}</strong>
          </li>
        </ul>
      </aside>
      <div className="overview-top-overlays">
        <OverviewClockPanel
          clocks={overviewClockSettings?.clocks}
          currentTime={currentTime}
          isError={isOverviewClockSettingsError}
          isLoading={isLoadingOverviewClockSettings}
        />
        <OverviewMetricsPanel status={status} telemetryState={telemetryState} />
      </div>
      <div className="overview-bottom-overlays">
        <UpcomingPoisPanel
          state={upcomingPoiState}
          pois={upcomingPoiView.topFive}
          currentTime={new Date(currentTime)}
        />
      </div>
      <Canvas camera={{ position: GEO_ANALYSIS_CAMERA_POSITION, fov: 45 }}>
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
          speed={1.1}
        />
        <Stars
          radius={50}
          depth={0}
          count={1500}
          factor={3}
          saturation={0}
          fade
          speed={0.75}
        />
        <Stars
          radius={50}
          depth={0}
          count={1500}
          factor={3}
          saturation={0}
          fade
          speed={0.1}
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
                  ? `+${upcomingPoiLabelLayout.fallback.hiddenIds.length} POIs — see Upcoming POIs`
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
        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.05}
          minDistance={3}
          maxDistance={GEO_ANALYSIS_MAX_DISTANCE}
        />
      </Canvas>
    </main>
  );
}
