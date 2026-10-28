import { useRef, useMemo } from 'react';
import * as THREE from 'three';
import { CityLitGlobe } from '../../pages/CityLitGlobe';
import { AnimatedFlowLine } from '../../pages/AnimatedFlowLine';
import { StarMarker } from '../../pages/OverviewStarMarker';
import { OverviewMapLabel } from '../../pages/OverviewMapLabel';
import { OverviewLabelLayout } from '../../pages/OverviewLabelLayout';
import { globePosition } from '../../pages/globe-coordinates';
import { SUN, ROUTE, LINKS, POIS, TRAFFIC, WIND_PATHS } from './scenario';
import { OverviewBloomMode } from '../../pages/overview-bloom-mode';
import { seededRandom } from './contracts';
import type { FlowEmitterConfig } from '../../pages/overview-animated-flow-line-rendering';

const FLOW: FlowEmitterConfig = {
  enabled: true,
  rate: 12,
  speed: 0.7,
  color: '#ffb000',
  size: 7,
  brightness: 1.5,
  maxParticles: 64,
  maxWorldSize: 0.045,
};
const QUIET = { color: '#5ea0aa', linewidth: 1, opacity: 0.3 };
const INVISIBLE = { color: '#5ea0aa', linewidth: 0, opacity: 0 };
function FixtureFlow({
  index,
  points,
  step,
}: {
  index: number;
  points: typeof ROUTE;
  step: number;
}) {
  const random = useMemo(() => seededRandom(429 + index), [index]);
  return (
    <AnimatedFlowLine
      points={points}
      forward={FLOW}
      reverse={FLOW}
      random={random}
      replayStep={step}
    />
  );
}
export function Fixture({
  full,
  paused,
  onPick,
}: {
  full: boolean;
  paused: boolean;
  onPick: (id: string) => void;
}) {
  const globe = useRef<THREE.Group>(null!);
  return (
    <>
      <color attach="background" args={['#030307']} />
      <ambientLight intensity={0.5} />
      <directionalLight position={SUN} intensity={5} />
      <group ref={globe}>
        <CityLitGlobe sunPosition={SUN} />
      </group>
      <OverviewLabelLayout paths={[ROUTE, ...LINKS]} />
      <FixtureFlow index={0} points={ROUTE} step={paused ? 0 : 1 / 60} />
      {LINKS.map((points, index) => (
        <FixtureFlow
          key={index}
          index={index + 1}
          points={points}
          step={paused ? 0 : 1 / 60}
        />
      ))}
      {POIS.map((poi) => (
        <group
          key={poi.id}
          onClick={(event) => {
            event.stopPropagation();
            onPick(poi.id);
          }}
        >
          <StarMarker coordinate={poi} size={0.1} color={poi.color} />
          <OverviewMapLabel
            id={poi.id}
            kind="poi"
            text={`SYN ${poi.id.toUpperCase()}`}
            position={globePosition(poi.latitude, poi.longitude, 2.006)}
            globeOccluder={globe}
            color={poi.color}
          />
        </group>
      ))}
      <StarMarker
        coordinate={{ latitude: 32, longitude: -65 }}
        color="#72b7ff"
        size={0.1}
        shape="chevron"
        ownAircraft
        headingDegrees={75}
      />
      {full && (
        <>
          {TRAFFIC.map((aircraft) => (
            <StarMarker
              key={aircraft.id}
              coordinate={aircraft}
              color="#8bd3ff"
              size={0.08}
              shape="chevron"
              chevronSizePixels={10}
              headingDegrees={aircraft.heading}
            />
          ))}
          <OverviewBloomMode value={false}>
            {WIND_PATHS.map((points, index) => (
              <AnimatedFlowLine
                key={index}
                points={points}
                outer={INVISIBLE}
                glow={INVISIBLE}
                core={QUIET}
              />
            ))}
          </OverviewBloomMode>
          {/* Synthetic bright-weather specimen, not live weather or a full GFS replay. */}
          <mesh
            position={globePosition(12, -40, 2.012)}
            rotation={[0, Math.PI / 2 - (40 * Math.PI) / 180, 0]}
          >
            <circleGeometry args={[0.35, 32]} />
            <meshBasicMaterial
              color="#e4efff"
              transparent
              opacity={0.4}
              depthWrite={false}
              side={THREE.DoubleSide}
              toneMapped={false}
            />
          </mesh>
          <mesh
            position={globePosition(50, -65, 2.015)}
            rotation={[0, Math.PI / 2 - (65 * Math.PI) / 180, 0]}
          >
            <ringGeometry args={[0.25, 0.4, 6]} />
            <meshBasicMaterial
              color="#e8c846"
              transparent
              opacity={0.5}
              depthWrite={false}
              side={THREE.DoubleSide}
              toneMapped={false}
            />
          </mesh>
        </>
      )}
    </>
  );
}
