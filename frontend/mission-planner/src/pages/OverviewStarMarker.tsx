import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import {
  CORE_COLOR,
  DEFAULT_GLOW_SIZE_PIXELS,
  createStarMarkerHaloResources,
  disposeStarMarkerHaloResources,
  projectedCoreRadius,
  resolveStarMarkerPosition,
  setStarMarkerHaloPixelRatio,
  type StarMarkerPositionProps,
} from './overview-star-marker-rendering';

const DEFAULT_CORE_RADIUS = 0.012;
const DEFAULT_GLOW_INTENSITY = 1;
const DEFAULT_MAX_CORE_PIXELS = 3;

export type StarMarkerProps = StarMarkerPositionProps & {
  color: string;
  size: number;
  coreColor?: string;
  coreRadius?: number;
  glowSizePixels?: number;
  glowIntensity?: number;
  lightColor?: string;
  lightIntensity?: number;
  lightDistance?: number;
  lightDecay?: number;
  maxCorePixels?: number;
};

function PhysicalCore({
  color,
  configuredRadius,
  maxCorePixels,
  position,
}: {
  color: string;
  configuredRadius: number;
  maxCorePixels: number;
  position: [number, number, number];
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const worldPosition = useMemo(() => new THREE.Vector3(), []);

  useFrame((state) => {
    if (!(state.camera instanceof THREE.PerspectiveCamera) || !mesh.current) {
      return;
    }

    mesh.current.getWorldPosition(worldPosition);
    const distance = state.camera.position.distanceTo(worldPosition);
    const radius = projectedCoreRadius({
      configuredRadius,
      maxCorePixels,
      distance,
      cameraFovDegrees: state.camera.fov,
      viewportHeight: state.size.height,
    });
    mesh.current.scale.setScalar(radius);
  });

  return (
    <mesh
      ref={mesh}
      position={position}
      scale={configuredRadius}
      renderOrder={5}
    >
      <sphereGeometry args={[1, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={8}
        roughness={0.15}
        toneMapped={false}
      />
    </mesh>
  );
}

export function StarMarker(props: StarMarkerProps) {
  const {
    color,
    size,
    coreColor = CORE_COLOR,
    coreRadius = Math.min(DEFAULT_CORE_RADIUS, size),
    glowSizePixels = Math.max(DEFAULT_GLOW_SIZE_PIXELS, size * 260),
    glowIntensity = DEFAULT_GLOW_INTENSITY,
    lightColor = color,
    lightIntensity = 0,
    lightDistance = 0.7,
    lightDecay = 2,
    maxCorePixels = DEFAULT_MAX_CORE_PIXELS,
  } = props;
  const position = resolveStarMarkerPosition(props);
  const halo = useMemo(
    () =>
      createStarMarkerHaloResources({
        color,
        glowSizePixels,
        glowIntensity,
      }),
    [color, glowIntensity, glowSizePixels]
  );

  useEffect(() => {
    return () => {
      disposeStarMarkerHaloResources(halo);
    };
  }, [halo]);

  useFrame((state) => {
    setStarMarkerHaloPixelRatio(halo, state.gl.getPixelRatio());
  });

  return (
    <>
      {halo.layers.map((layer) => (
        <points
          key={layer.renderOrder}
          position={position}
          geometry={halo.geometry}
          material={layer.material}
          renderOrder={layer.renderOrder}
        />
      ))}
      <PhysicalCore
        color={coreColor}
        configuredRadius={coreRadius}
        maxCorePixels={maxCorePixels}
        position={position}
      />
      {lightIntensity > 0 && (
        <pointLight
          color={lightColor}
          intensity={lightIntensity}
          distance={lightDistance}
          decay={lightDecay}
          position={position}
          castShadow={false}
        />
      )}
    </>
  );
}
