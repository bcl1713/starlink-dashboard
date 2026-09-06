import { Suspense, useEffect, useMemo } from 'react';
import { Canvas, useLoader } from '@react-three/fiber';
import { Line, OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';
import './OverviewPage.css';
import { greatCirclePoints, type GlobeCoordinate } from './globe-route';
import { globePosition } from './globe-coordinates';

const demoRouteEndpoints = {
  origin: { latitude: 41.8781, longitude: -87.6298 },
  destination: { latitude: 51.5072, longitude: -0.1276 },
} as const;

const chicagoToLondonRoute = greatCirclePoints(
  demoRouteEndpoints.origin,
  demoRouteEndpoints.destination,
  2.02,
  64
);

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

function DemoRoute() {
  return (
    <Line
      points={chicagoToLondonRoute}
      color="#ffb000"
      lineWidth={2}
      transparent
      opacity={0.85}
      depthWrite={false}
    />
  );
}

interface RouteEndpointProps {
  coordinate: GlobeCoordinate;
  color: string;
}

function RouteEndpoint({ coordinate, color }: RouteEndpointProps) {
  return (
    <mesh
      position={globePosition(coordinate.latitude, coordinate.longitude, 2.0)}
    >
      <sphereGeometry args={[0.035, 24, 24]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

function Globe() {
  const sourceTexture = useLoader(THREE.TextureLoader, '/earth-night.jpg');

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
      <meshStandardMaterial
        map={colorMap}
        emissive="#ffffff"
        emissiveMap={colorMap}
        emissiveIntensity={0.75}
        roughness={0.8}
        metalness={0.05}
      />
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
  return (
    <main className="overview-page">
      <aside className="globe-legend" aria-label="Route legend">
        <p className="globe-legend__title">Demo route</p>
        <ul className="globe-legend__items">
          <li>
            <span
              className="globe-legend__marker globe-legend__marker--origin"
              aria-hidden="true"
            />
            <span>Origin</span>
            <strong>Chicago</strong>
          </li>
          <li>
            <span
              className="globe-legend__marker globe-legend__marker--destination"
              aria-hidden="true"
            />
            <span>Destination</span>
            <strong>London</strong>
          </li>
          <li>
            <span className="globe-legend__route" aria-hidden="true" />
            <span>Path</span>
            <strong>Great-circle route</strong>
          </li>
        </ul>
      </aside>
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }}>
        <color attach="background" args={['#030307']} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[5, 3, 5]} intensity={1.4} />
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
          <DemoRoute />
          <RouteEndpoint
            coordinate={demoRouteEndpoints.origin}
            color="#ffb000"
          />
          <RouteEndpoint
            coordinate={demoRouteEndpoints.destination}
            color="#62d9ff"
          />
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
