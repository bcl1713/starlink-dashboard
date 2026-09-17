import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import {
  CORE_COLOR,
  createStarMarkerHaloResources,
  disposeStarMarkerHaloResources,
  projectedCoreRadius,
  resolveStarMarkerPosition,
  type StarMarkerPositionProps,
} from './overview-star-marker-rendering';

const DEFAULT_CORE_RADIUS = 0.02;
const DEFAULT_GLOW_INTENSITY = 0.85;
const DEFAULT_MAX_CORE_PIXELS = 4;

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
  const camera = useThree((state) => state.camera);

  useFrame((state) => {
    if (!(camera instanceof THREE.PerspectiveCamera) || !mesh.current) {
      return;
    }

    const distance = camera.position.distanceTo(mesh.current.position);
    const radius = projectedCoreRadius({
      configuredRadius,
      maxCorePixels,
      distance,
      cameraFovDegrees: camera.fov,
      viewportHeight: state.size.height,
    });
    mesh.current.scale.setScalar(radius);
  });

  return (
    <mesh
      ref={mesh}
      position={position}
      scale={configuredRadius}
      renderOrder={2}
    >
      <sphereGeometry args={[1, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={2}
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
    glowSizePixels = Math.max(1, size * 200),
    glowIntensity = DEFAULT_GLOW_INTENSITY,
    lightColor = color,
    lightIntensity = 0,
    lightDistance = 0,
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
    halo.material.uniforms.uPixelRatio.value = state.gl.getPixelRatio();
  });

  return (
    <>
      <points
        position={position}
        geometry={halo.geometry}
        material={halo.material}
        renderOrder={1}
      />
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
