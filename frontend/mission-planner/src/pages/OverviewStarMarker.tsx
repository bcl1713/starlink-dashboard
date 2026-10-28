import {
  useOverviewBloom,
  useOverviewBloomEmission,
} from './overview-bloom-mode';
import { useEffect, useMemo, useRef } from 'react';
import {
  starMarkerPickRaycast,
  ignoreStarMarkerRaycast,
} from './overview-star-marker-picking';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import {
  CORE_COLOR,
  createStarMarkerChevronResources,
  isStarMarkerVisible,
  starMarkerHeadingDirection,
  updateStarMarkerChevronStyle,
  setStarMarkerChevronMatrix,
  setStarMarkerChevronBloom,
  DEFAULT_GLOW_SIZE_PIXELS,
  createStarMarkerHaloResources,
  disposeStarMarkerHaloResources,
  projectedCoreRadius,
  resolveStarMarkerPosition,
  setStarMarkerHaloPixelRatio,
  type StarMarkerPositionProps,
} from './overview-star-marker-rendering';

import {
  DEFAULT_CHEVRON_SETTINGS,
  type ChevronSettings,
} from './overview-chevron-settings';

const DEFAULT_CORE_RADIUS = 0.012;
const DEFAULT_GLOW_INTENSITY = 1;
const DEFAULT_MAX_CORE_PIXELS = 3;

export type StarMarkerProps = StarMarkerPositionProps & {
  color: string;
  size: number;
  shape?: 'star' | 'chevron';
  chevronSizePixels?: number;
  headingDegrees?: number;
  chevronSettings?: Readonly<ChevronSettings>;
  renderOrder?: number;
  ownAircraft?: boolean;
  coreColor?: string;
  coreRadius?: number;
  glowSizePixels?: number;
  glowIntensity?: number;
  lightColor?: string;
  lightIntensity?: number;
  lightDistance?: number;
  lightDecay?: number;
  maxCorePixels?: number;
  /** Optional experiment hit target in CSS pixels; independent of visual halos. */
  pickRadiusPixels?: number;
};

function PhysicalCore({
  color,
  emissionColor,
  emissionIntensity,
  raycast,
  configuredRadius,
  maxCorePixels,
  position,
}: {
  color: string;
  emissionColor: string;
  emissionIntensity: number;
  raycast: THREE.Mesh['raycast'];
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
      raycast={raycast}
      position={position}
      scale={configuredRadius}
      renderOrder={5}
    >
      <sphereGeometry args={[1, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={emissionColor}
        emissiveIntensity={emissionIntensity}
        roughness={0.15}
        toneMapped={false}
      />
    </mesh>
  );
}

function StarMarkerPickTarget({
  position,
  radiusPixels,
}: {
  position: [number, number, number];
  radiusPixels: number;
}) {
  const height = useThree((state) => state.size.height);
  const raycast = useMemo(
    () => starMarkerPickRaycast(radiusPixels, height),
    [radiusPixels, height]
  );
  return (
    <object3D
      name="overview-star-pick-target"
      position={position}
      raycast={raycast}
    />
  );
}

function GlowingStarMarker(props: StarMarkerProps) {
  const bloom = useOverviewBloom();
  const emission = useOverviewBloomEmission();
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
      {!bloom &&
        halo.layers.map((layer) => (
          <points
            key={layer.renderOrder}
            position={position}
            geometry={halo.geometry}
            material={layer.material}
            raycast={
              props.pickRadiusPixels !== undefined
                ? ignoreStarMarkerRaycast
                : THREE.Points.prototype.raycast
            }
            renderOrder={layer.renderOrder}
          />
        ))}
      <PhysicalCore
        color={coreColor}
        emissionColor={bloom ? color : coreColor}
        emissionIntensity={bloom ? emission.pois : 8}
        raycast={
          props.pickRadiusPixels !== undefined
            ? ignoreStarMarkerRaycast
            : THREE.Mesh.prototype.raycast
        }
        configuredRadius={coreRadius}
        maxCorePixels={maxCorePixels}
        position={position}
      />
      {props.pickRadiusPixels !== undefined && (
        <StarMarkerPickTarget
          position={position}
          radiusPixels={props.pickRadiusPixels}
        />
      )}
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

function ChevronMarker(props: StarMarkerProps) {
  const bloom = useOverviewBloom();
  const emission = useOverviewBloomEmission();
  const mesh = useRef<THREE.Mesh>(null);
  const position = resolveStarMarkerPosition(props);
  const headingDirection = starMarkerHeadingDirection(
    position,
    props.headingDegrees
  );
  const worldPosition = useMemo(() => new THREE.Vector3(), []);
  const resources = useMemo(
    () =>
      createStarMarkerChevronResources({
        color: props.color,
        coreColor: props.coreColor ?? CORE_COLOR,
        glowIntensity: props.glowIntensity ?? DEFAULT_GLOW_INTENSITY,
      }),
    [props.color, props.coreColor, props.glowIntensity]
  );
  useEffect(
    () => () => {
      resources.geometry.dispose();
      resources.material.dispose();
      resources.haloGeometry.dispose();
      resources.haloMaterial.dispose();
    },
    [resources]
  );
  const settings = props.chevronSettings ?? DEFAULT_CHEVRON_SETTINGS;
  const sizePixels = props.chevronSizePixels ?? settings.ownSizePixels;
  useEffect(() => {
    updateStarMarkerChevronStyle(resources, settings, sizePixels);
    setStarMarkerChevronBloom(resources, bloom, emission.aircraft);
  }, [bloom, emission.aircraft, resources, settings, sizePixels]);
  useFrame((state) => {
    if (!mesh.current) return;
    state.camera.updateMatrixWorld();
    worldPosition.set(...position);
    mesh.current.visible = isStarMarkerVisible(worldPosition, state.camera);
    setStarMarkerChevronMatrix(
      mesh.current.matrix,
      worldPosition,
      headingDirection,
      state.camera,
      state.size.height,
      sizePixels
    );
    mesh.current.matrixWorldNeedsUpdate = true;
  });
  return (
    <mesh
      ref={mesh}
      name={props.ownAircraft ? 'overview-own-aircraft' : undefined}
      geometry={resources.geometry}
      material={resources.material}
      matrixAutoUpdate={false}
      dispose={null}
      userData={{ starMarkerShape: 'chevron' }}
      renderOrder={props.renderOrder ?? 1000}
    >
      {!bloom && (
        <mesh
          geometry={resources.haloGeometry}
          material={resources.haloMaterial}
          renderOrder={(props.renderOrder ?? 1000) - 1}
          frustumCulled={false}
          raycast={() => {}}
          dispose={null}
        />
      )}
    </mesh>
  );
}

export function StarMarker(props: StarMarkerProps) {
  return props.shape === 'chevron' ? (
    <ChevronMarker {...props} />
  ) : (
    <GlowingStarMarker {...props} />
  );
}
