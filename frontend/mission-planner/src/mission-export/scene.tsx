import { Suspense, useEffect, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { CityLitGlobe } from '../pages/CityLitGlobe';
import { GlobeRouteRibbon } from '../pages/GlobeRouteRibbon';
import { sunLightPosition } from '../pages/solar-position';
import {
  applyCameraFrame,
  MAP_HEIGHT,
  MAP_WIDTH,
  type MissionMapView,
} from './framing';
import type { MissionMapInput } from './protocol';

const NEUTRAL = {
  color: '#f4f4f4',
  widthPixels: 4,
  maxWorldWidth: 0.028,
  opacity: 1,
};
const HALO = {
  color: '#252525',
  widthPixels: 8,
  maxWorldWidth: 0.05,
  opacity: 1,
};
type Label = {
  text: string;
  x: number;
  y: number;
  anchorX?: number;
  anchorY?: number;
};
function projectLabels(camera: THREE.Camera, view: MissionMapView): Label[] {
  const candidates = [
    {
      text: view.startIndex === 0 ? 'Start' : 'Continues',
      point: view.points[0],
    },
    { text: view.endsRoute ? 'End' : 'Continues', point: view.points.at(-1)! },
    ...view.markers.map((m) => ({ text: m.label, point: m.point })),
  ];
  const labels: Label[] = [];
  for (const { text, point } of candidates) {
    const p = new THREE.Vector3(...point).project(camera);
    const x = ((p.x + 1) * MAP_WIDTH) / 2,
      y = ((1 - p.y) * MAP_HEIGHT) / 2;
    const width = text.length * 48 + 48;
    const offsets = [
      [0, -112],
      [0, 112],
    ];
    for (let ring = 1; ring <= 4; ring++) {
      for (const dy of [0, -112 * ring, 112 * ring]) {
        offsets.push([width * ring, dy], [-width * ring, dy]);
      }
      offsets.push([0, -112 * ring], [0, 112 * ring]);
    }
    const candidate = offsets
      .map(([dx, dy]) => ({ text, x: x + dx, y: y + dy }))
      .find(
        (l) =>
          l.x - width / 2 >= 64 &&
          l.x + width / 2 <= MAP_WIDTH - 64 &&
          l.y >= 128 &&
          l.y <= MAP_HEIGHT - 128 &&
          labels.every(
            (other) =>
              Math.abs(other.x - l.x) >
                (width + other.text.length * 48 + 48) / 2 ||
              Math.abs(other.y - l.y) > 104
          )
      );
    if (!candidate)
      throw new Error('Projected labels cannot fit without overlap');
    labels.push({ ...candidate, anchorX: x, anchorY: y });
  }
  return labels;
}
function ReadyScene({
  view,
  digest,
  onLabels,
}: {
  view: MissionMapView;
  digest: string;
  onLabels: (labels: Label[]) => void;
}) {
  const { gl, scene, camera, invalidate } = useThree();
  const prepared = useRef(false);
  const frames = useRef(0);
  useEffect(() => {
    let active = true;
    const canvas = gl.domElement;
    const lost = () => {
      window.missionMap.state = {
        status: 'error',
        error: 'WebGL context lost',
        digest,
      };
    };
    canvas.addEventListener('webglcontextlost', lost);
    void (async () => {
      try {
        applyCameraFrame(camera as THREE.PerspectiveCamera, view);
        const images = new Set<HTMLImageElement>();
        scene.traverse((object) => {
          const material = (object as THREE.Mesh).material;
          for (const m of Array.isArray(material) ? material : [material]) {
            if (!m) continue;
            const map = (m as THREE.MeshStandardMaterial).map;
            if (map?.image instanceof HTMLImageElement) images.add(map.image);
          }
        });
        // useLoader has resolved both local textures; decode their source images
        // explicitly, including the city mask used by onBeforeCompile.
        for (const image of document.images) if (image.src) images.add(image);
        if (images.size < 2) {
          // TextureLoader's source cache carries the second shader-only mask.
          const textures = await Promise.all(
            ['/earth-day-hi.jpg', '/city-lights-mask.png'].map(async (src) => {
              const image = new Image();
              image.src = src;
              await image.decode();
              return image;
            })
          );
          textures.forEach((image) => images.add(image));
        }
        await Promise.all([...images].map((image) => image.decode()));
        await document.fonts.ready;
        await gl.compileAsync(scene, camera);
        if (gl.getContext().isContextLost())
          throw new Error('WebGL context lost');
        if (
          gl.info.programs?.some(
            (program) =>
              !gl
                .getContext()
                .getProgramParameter(
                  program.program as WebGLProgram,
                  gl.getContext().LINK_STATUS
                )
          )
        )
          throw new Error('Shader compilation failed');
        if (!active || window.missionMap.state.status === 'error') return;
        const labels = projectLabels(camera, view);
        onLabels(labels);
        prepared.current = true;
        invalidate();
      } catch (error) {
        if (active && window.missionMap.state.status !== 'error')
          window.missionMap.state = {
            status: 'error',
            error: `Readiness/texture error: ${String(error)}`,
            digest,
          };
      }
    })();
    return () => {
      active = false;
      canvas.removeEventListener('webglcontextlost', lost);
    };
  }, [camera, digest, gl, invalidate, onLabels, scene, view]);
  useFrame(() => {
    if (!prepared.current || window.missionMap.state.status === 'error') return;
    gl.render(scene, camera);
    gl.getContext().finish();
    frames.current++;
    // First draw settles ribbon width uniforms; following draws confirm the
    // unchanged static camera/geometry. Demand frames, never a readiness sleep.
    if (frames.current < 3) {
      invalidate();
      return;
    }
    window.missionMap.state = {
      status: 'ready',
      digest,
      viewId: view.id,
      framing: {
        direction: view.direction,
        distance: view.distance,
        offsetX: view.offsetX,
        offsetY: view.offsetY,
        startIndex: view.startIndex,
        endIndex: view.endIndex,
      },
      labels: projectLabels(camera, view),
      stages: [
        'textures-decoded',
        'shaders-compiled',
        'camera-settled',
        'labels-projected',
        'render-complete',
      ],
    };
  }, 1);
  return null;
}
export function MissionExportScene({
  input,
  view,
  digest,
}: {
  input: MissionMapInput;
  view: MissionMapView;
  digest: string;
}) {
  const [labels, setLabels] = useState<Label[]>([]);
  const sun = sunLightPosition(new Date(input.referenceUtc), 10);
  return (
    <div
      style={{
        position: 'relative',
        width: MAP_WIDTH,
        height: MAP_HEIGHT,
        background: '#101820',
        color: '#f4f4f4',
        fontFamily: 'DejaVu Sans, sans-serif',
      }}
    >
      <Canvas
        frameloop="demand"
        dpr={1}
        camera={{ fov: 38, near: 0.1, far: 100 }}
        gl={{ antialias: true, preserveDrawingBuffer: true }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={sun} intensity={5} />
        <Suspense fallback={null}>
          <CityLitGlobe sunPosition={sun} />
          <GlobeRouteRibbon
            points={view.points}
            outer={HALO}
            glow={NEUTRAL}
            core={NEUTRAL}
            depthTest
          />
          <ReadyScene view={view} digest={digest} onLabels={setLabels} />
        </Suspense>
      </Canvas>
      <svg
        width={MAP_WIDTH}
        height={MAP_HEIGHT}
        style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
      >
        {labels.map((label, i) => (
          <line
            key={i}
            x1={label.anchorX}
            y1={label.anchorY}
            x2={label.x}
            y2={label.y}
            stroke="#f4f4f4"
            strokeWidth={4}
          />
        ))}
      </svg>
      {labels.map((label, i) => (
        <div
          key={i}
          data-map-label
          style={{
            position: 'absolute',
            left: label.x,
            top: label.y,
            transform: 'translate(-50%, -50%)',
            padding: '4px 12px',
            background: '#f4f4f4',
            color: '#202020',
            borderRadius: 4,
            fontSize: 84,
            whiteSpace: 'nowrap',
          }}
        >
          {label.text}
        </div>
      ))}
    </div>
  );
}
