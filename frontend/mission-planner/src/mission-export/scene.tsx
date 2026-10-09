import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { CityLitGlobe } from '../pages/CityLitGlobe';
import { GlobeRouteRibbon } from '../pages/GlobeRouteRibbon';
import { StarMarker } from '../pages/OverviewStarMarker';
import { OverviewBoundaryLayer } from '../pages/OverviewBoundaryLayer';
import {
  parseBoundaries,
  projectBoundaries,
} from '../pages/overview-boundaries';
import countries from '../../public/boundaries/countries.json';
import { sunLightPosition } from '../pages/solar-position';
import { applyCameraFrame, type MissionMapView } from './framing';
import type { MissionMapInput } from './protocol';

// Pixel-sized globe overlays need to survive the high-resolution image being
// reduced to the 280px map column in the PDF.
const PDF_MAP_WIDTH = 280;
function projectEndpoints(camera: THREE.Camera, view: MissionMapView) {
  const endpoints = [
    ...(view.startIndex === 0
      ? [{ role: 'departure' as const, point: view.points[0] }]
      : []),
    ...(view.endsRoute
      ? [{ role: 'arrival' as const, point: view.points.at(-1)! }]
      : []),
  ];
  return endpoints.map(({ role, point }) => {
    const p = new THREE.Vector3(...point).project(camera);
    return {
      role,
      x: ((p.x + 1) * view.width) / 2,
      y: ((1 - p.y) * view.height) / 2,
    };
  });
}
function ReadyScene({
  view,
  digest,
}: {
  view: MissionMapView;
  digest: string;
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
  }, [camera, digest, gl, invalidate, scene, view]);
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
        width: view.width,
        height: view.height,
        direction: view.direction,
        distance: view.distance,
        offsetX: view.offsetX,
        offsetY: view.offsetY,
        startIndex: view.startIndex,
        endIndex: view.endIndex,
      },
      labels: [],
      endpoints: projectEndpoints(camera, view),
      stages: [
        'textures-decoded',
        'shaders-compiled',
        'camera-settled',
        'boundaries-ready',
        'endpoint-stars-projected',
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
  const boundaries = useMemo(
    () => projectBoundaries(parseBoundaries(countries)),
    []
  );
  const sun = sunLightPosition(new Date(input.referenceUtc), 10);
  const pixelScale = view.width / PDF_MAP_WIDTH;
  const routeStyle = useMemo(
    () => ({
      outer: {
        color: '#ffb000',
        widthPixels: 8 * pixelScale,
        maxWorldWidth: 0.05 * pixelScale,
        opacity: 0.18,
        blending: THREE.AdditiveBlending,
      },
      glow: {
        color: '#ffb000',
        widthPixels: 4 * pixelScale,
        maxWorldWidth: 0.028 * pixelScale,
        opacity: 0.5,
        blending: THREE.AdditiveBlending,
      },
      core: {
        color: '#ffd86b',
        widthPixels: 2 * pixelScale,
        maxWorldWidth: 0.012 * pixelScale,
        opacity: 1,
      },
    }),
    [pixelScale]
  );
  const endpointStyle = {
    color: '#ffffff',
    size: 0.13,
    coreRadius: 0.06,
    glowSizePixels: 24 * pixelScale,
    glowIntensity: 2.3,
    maxCorePixels: 6 * pixelScale,
  };
  return (
    <div
      style={{
        position: 'relative',
        width: view.width,
        height: view.height,
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
          <GlobeRouteRibbon points={view.points} {...routeStyle} depthTest />
          <OverviewBoundaryLayer kind="countries" segments={boundaries} />
          {view.startIndex === 0 && (
            <StarMarker position={view.points[0]} {...endpointStyle} />
          )}
          {view.endsRoute && (
            <StarMarker position={view.points.at(-1)!} {...endpointStyle} />
          )}
          <ReadyScene view={view} digest={digest} />
        </Suspense>
      </Canvas>
    </div>
  );
}
