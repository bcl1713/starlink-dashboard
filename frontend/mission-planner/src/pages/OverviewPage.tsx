import { Suspense, useEffect, useMemo, useState } from 'react';
import { Canvas, useLoader } from '@react-three/fiber';
import { Line, OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';
import './OverviewPage.css';
import { type GlobeCoordinate } from './globe-route';
import { activeRouteId } from './active-globe-route';
import { projectRouteArc } from './globe-route-projection';
import { useRoute, useRoutes } from '../hooks/api/useRoutes';
import { sunLightPosition } from './solar-position';
import { millisecondsUntilNextMinute } from './solar-clock';
import { useStatus } from '@/hooks/api/useStatus';
import { projectAircraftPosition } from './status-projection';
import { StarMarker } from './OverviewStarMarker';
import { isStatusStale } from './status-freshness';

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

interface RouteEndpointProps {
  coordinate: GlobeCoordinate;
  color: string;
}

function RouteEndpoint({ coordinate, color }: RouteEndpointProps) {
  return <StarMarker coordinate={coordinate} color={color} size={0.05} />;
}

function AircraftMarker({ coordinate }: { coordinate: GlobeCoordinate }) {
  return <StarMarker coordinate={coordinate} color="#72b7ff" size={0.065} />;
}

function Globe() {
  const sourceTexture = useLoader(THREE.TextureLoader, '/earth-day.jpg');

  const colorMap = useMemo(() => {
    const texture = sourceTexture.clone();

    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    return texture;
  }, [sourceTexture]);

  useEffect(() => {
    return () => {
      colorMap.dispose();
    };
  }, [colorMap]);

  return (
    <mesh>
      <sphereGeometry args={[2, 64, 64]} />
      <meshStandardMaterial map={colorMap} roughness={0.8} metalness={0.05} />
    </mesh>
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
    () => projectRouteArc(activeRoute?.points ?? [], 2.02, 8),
    [activeRoute?.points]
  );

  const origin = activeRoute?.points?.at(0);
  const destination = activeRoute?.points?.at(-1);

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

  const {
    data: status,
    isLoading: isLoadingStatus,
    error: statusError,
  } = useStatus();

  const aircraftPosition = projectAircraftPosition(status ?? {});

  const telemetryState = statusError
    ? 'Telemetry error'
    : isLoadingStatus
      ? 'Loading telemetry…'
      : !status
        ? 'Telemetry unavailable'
        : isStatusStale(status.timestamp, Date.now())
          ? 'Telemetry stale'
          : !aircraftPosition
            ? 'Position unavailable'
            : 'Live telemetry';

  return (
    <main className="overview-page">
      {routeStatus ? (
        <aside
          className="globe-legend"
          aria-label="Route status"
          role={routesError || routeError ? 'alert' : 'status'}
        >
          <p className="globe-legend__title">Route status</p>
          <p className="globe-legend__message">{routeStatus}</p>
        </aside>
      ) : (
        <aside className="globe-legend" aria-label="Active route legend">
          <p className="globe-legend__title">Active route</p>
          <ul className="globe-legend__items">
            <li>
              <span
                className="globe-legend__marker globe-legend__marker--origin"
                aria-hidden="true"
              />
              <span>Origin</span>
              <strong>First route point</strong>
            </li>
            <li>
              <span
                className="globe-legend__marker globe-legend__marker--destination"
                aria-hidden="true"
              />
              <span>Destination</span>
              <strong>Last route point</strong>
            </li>
            <li>
              <span
                className="globe-legend__marker globe-legend__marker--aircraft"
                aria-hidden="true"
              />
              <span>Current aircraft position</span>
              <strong>{telemetryState}</strong>
            </li>
            <li>
              <span className="globe-legend__route" aria-hidden="true" />
              <span>Path</span>
              <strong>{activeRoute?.name}</strong>
            </li>
          </ul>
        </aside>
      )}
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }}>
        <color attach="background" args={['#030307']} />
        <ambientLight intensity={0.02} />
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
          <Globe />
          <Atmosphere />
          {hasRenderableRoute && (
            <Line
              points={routePoints}
              color="#ffb000"
              linewidth={2}
              transparent
              opacity={0.85}
              depthWrite={false}
            />
          )}
          {origin && <RouteEndpoint coordinate={origin} color="#ffb000" />}
          {destination && (
            <RouteEndpoint coordinate={destination} color="#00ff00" />
          )}
          {aircraftPosition && <AircraftMarker coordinate={aircraftPosition} />}
        </Suspense>
        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.05}
          minDistance={3}
          maxDistance={10}
        />
      </Canvas>
    </main>
  );
}
