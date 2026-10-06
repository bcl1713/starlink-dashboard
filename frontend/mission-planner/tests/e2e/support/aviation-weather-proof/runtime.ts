import * as THREE from 'three';
import type { RootState } from '@react-three/fiber';
import {
  Allocation,
  decodePayload,
  labels,
  type Descriptor,
  type Payload,
} from './model';
import { gridMesh, windBarbs, earthPoint } from './grid-renderer';
import { advisoryMesh, type Feature } from './advisory-renderer';
import { sampleGrid } from './sampling';
const allocation = new Allocation();
const win = window as unknown as {
  __overviewEvidenceRoots: { containerInfo?: { getState?: () => RootState } }[];
  aviationProof: unknown;
};
const state = () => {
  const s = win.__overviewEvidenceRoots
    .find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
    ?.containerInfo?.getState?.();
  if (!s) throw Error('Native Overview not observed');
  return s;
};
type Owned = { mesh: THREE.Object3D; dispose: () => void };
let installed:
  | {
      d: Descriptor;
      values?: Int16Array;
      mask?: Uint8Array;
      objects: Owned[];
      releases: (() => void)[];
      label: HTMLElement;
      saved: { position: THREE.Vector3; target: THREE.Vector3 };
    }
  | undefined;
function controls() {
  return state().controls as unknown as {
    setLookAt: (...n: (number | boolean)[]) => void;
    update: (n: number) => void;
    getTarget: () => THREE.Vector3;
  };
}
function look(latitude: number, longitude: number, radius = 5) {
  const p = earthPoint(latitude, longitude, radius);
  controls().setLookAt(p.x, p.y, p.z, 0, 0, 0, false);
  controls().update(0);
  state().camera.updateMatrixWorld();
  state().invalidate();
}
async function install(url: string) {
  const controller = new AbortController(),
    deadline = setTimeout(() => controller.abort(), 45000);
  const objects: Owned[] = [],
    releases: (() => void)[] = [];
  let label: HTMLElement | undefined;
  try {
    const base = new URL(url, location.href);
    if (
      base.origin !== location.origin ||
      !base.pathname.startsWith('/api/overview-weather/aviation-proof-assets/')
    )
      throw Error('confined fixture URL required');
    const response = await fetch(base, { signal: controller.signal });
    if (!response.ok) throw Error('descriptor HTTP');
    const text = await response.text();
    if (text.length > 1024 * 1024) throw Error('descriptor budget');
    const d = JSON.parse(text) as Descriptor;
    if (d.schema !== 'aviation-weather-v1') throw Error('schema');
    const fetchPayload = async (p: Payload) => {
      if (
        !p.path ||
        !/^[a-z][a-z0-9.-]*$/.test(p.path) ||
        p.byte_size > 16 * 1024 ** 2
      )
        throw Error('payload path/budget');
      const r = await fetch(new URL(p.path, base), {
        signal: controller.signal,
      });
      if (!r.ok) throw Error('payload HTTP');
      const b = await r.arrayBuffer();
      return b;
    };
    let values: Int16Array | undefined, mask: Uint8Array | undefined;
    if (d.representation === 'latlon-grid-v1') {
      const g = d.grid;
      if (
        g.width < 1 ||
        g.width > 720 ||
        g.height < 1 ||
        g.height > 361 ||
        g.longitude_start !== -180 ||
        g.longitude_step !== 0.5 ||
        g.latitude_start !== 90 ||
        g.latitude_step !== -0.5
      )
        throw Error('unsupported grid');
      const cells = g.width * g.height,
        entries = Object.entries(d.components);
      if (entries.length > 3 || !d.components.t) throw Error('components');
      const encoded =
        entries.reduce((s, [, p]) => s + p.byte_size, 0) + d.mask.byte_size;
      releases.push(allocation.reserve(encoded, encoded * 2, 0));
      const results = await Promise.all([
        ...entries.map(
          async ([k, p]) =>
            [k, await decodePayload(await fetchPayload(p), p, cells)] as const
        ),
        (async () =>
          [
            'mask',
            await decodePayload(await fetchPayload(d.mask), d.mask, cells),
          ] as const)(),
      ]);
      const arrays = Object.fromEntries(results);
      values = arrays.t as Int16Array;
      mask = arrays.mask as Uint8Array;
      if (mask.some((x) => x > 3)) throw Error('mask');
      // Reserve conservative geometry and packed texture bytes BEFORE constructors.
      const gridReserve = allocation.reserve(
        0,
        cells * 4 + 1_000_000,
        cells * 4 + 1_000_000
      );
      releases.push(gridReserve);
      const scalar = gridMesh(d, values, mask);
      objects.push(scalar);
      if (arrays.u && arrays.v) {
        releases.push(allocation.reserve(0, 1_000_000, 1_000_000));
        objects.push(
          windBarbs(d, arrays.u as Int16Array, arrays.v as Int16Array, mask)
        );
      }
    } else if (d.representation === 'advisory-v1') {
      const p = d.advisories!;
      releases.push(
        allocation.reserve(p.byte_size, p.byte_size * 4 + 4_800_000, 4_800_000)
      );
      const bytes = await fetchPayload(p);
      await decodePayload(bytes, { ...p, dtype: 'uint8' }, p.byte_size);
      const collection = JSON.parse(new TextDecoder().decode(bytes)) as {
        features: Feature[];
      };
      if (collection.features.length > 500) throw Error('advisory count');
      objects.push(
        advisoryMesh(
          collection.features,
          d.diagnostic_replay_at_ms ?? Date.now()
        )
      );
    } else throw Error('representation');
    const s = state();
    const saved = installed?.saved ?? {
      position: s.camera.position.clone(),
      target: controls().getTarget().clone(),
    };
    // Replacement is allocated while the old generation remains owned; accounting
    // covers both. A failed candidate leaves the prior visualization intact.
    dispose(false);
    label = document.createElement('aside');
    label.dataset.aviationProof = 'true';
    label.style.cssText =
      'position:fixed;z-index:9999;bottom:10px;left:12px;max-width:900px;background:#101829ee;color:white;font:12px sans-serif;padding:10px;pointer-events:none';
    label.textContent = `DIAGNOSTIC • ${labels(d)} • ${(d.attribution ?? []).join('; ')}`;
    document.body.append(label);
    for (const object of objects) s.scene.add(object.mesh);
    installed = { d, values, mask, objects, releases, label, saved };
    s.invalidate();
    return snapshot();
  } catch (error) {
    for (const object of objects) object.dispose();
    for (const release of releases) release();
    label?.remove();
    throw error;
  } finally {
    clearTimeout(deadline);
  }
}
function dispose(restore = true) {
  if (!installed) return;
  const old = installed;
  installed = undefined;
  for (const o of old.objects) {
    o.mesh.removeFromParent();
    o.dispose();
  }
  for (const release of old.releases) release();
  old.label.remove();
  if (restore) {
    const p = old.saved.position,
      t = old.saved.target;
    controls().setLookAt(p.x, p.y, p.z, t.x, t.y, t.z, false);
    controls().update(0);
  }
  state().invalidate();
}
function snapshot() {
  const s = state(),
    gl = s.gl.getContext();
  return {
    allocation: {
      current: { ...allocation.current },
      peak: { ...allocation.peak },
    },
    label: installed?.label.textContent,
    objects: installed?.objects.map((o) => ({
      name: o.mesh.name,
      geometryBytes:
        'geometry' in o.mesh
          ? Object.values((o.mesh as THREE.Mesh).geometry.attributes).reduce(
              (n, a) => n + a.array.byteLength,
              0
            )
          : 0,
    })),
    camera: {
      position: s.camera.position.toArray(),
      projection: s.camera.projectionMatrix.toArray(),
    },
    viewport: {
      width: gl.drawingBufferWidth,
      height: gl.drawingBufferHeight,
      dpr: devicePixelRatio,
    },
    renderer: {
      version: gl.getParameter(gl.VERSION),
      renderer: gl.getParameter(gl.RENDERER),
    },
    memory: { ...s.gl.info.memory },
  };
}
function sample(latitude: number, longitude: number) {
  if (!installed?.values || !installed.mask) throw Error('scalar required');
  const scalar = installed.objects[0].mesh as THREE.Mesh<
    THREE.SphereGeometry,
    THREE.ShaderMaterial
  >;
  const s = state();
  look(latitude, longitude);
  s.scene.updateMatrixWorld(true);
  const gl = s.gl.getContext(),
    width = gl.drawingBufferWidth,
    height = gl.drawingBufferHeight;
  const projected = earthPoint(latitude, longitude).project(s.camera),
    x = Math.floor((projected.x * 0.5 + 0.5) * width),
    y = Math.floor((projected.y * 0.5 + 0.5) * height);
  if (x < 0 || x >= width || y < 0 || y >= height)
    throw Error('sample off viewport');
  const ndc = new THREE.Vector2(
      ((x + 0.5) / width) * 2 - 1,
      ((y + 0.5) / height) * 2 - 1
    ),
    ray = new THREE.Raycaster();
  ray.setFromCamera(ndc, s.camera);
  const hit = ray.intersectObject(scalar, false)[0];
  if (!hit) throw Error('sample misses tessellated native mesh');
  const p = scalar.worldToLocal(hit.point.clone()),
    sampleLatitude = (Math.asin(p.y / p.length()) * 180) / Math.PI,
    sampleLongitude = (Math.atan2(-p.z, p.x) * 180) / Math.PI;
  const camera = s.camera.clone();
  const matrix = camera.projectionMatrix.elements;
  // Exact one-pixel crop of the independently rounded native framebuffer pixel.
  for (let col = 0; col < 4; col++) {
    matrix[col * 4] = width * (matrix[col * 4] - ndc.x * matrix[col * 4 + 3]);
    matrix[col * 4 + 1] =
      height * (matrix[col * 4 + 1] - ndc.y * matrix[col * 4 + 3]);
  }
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  camera.updateMatrixWorld();
  const release = allocation.reserve(0, 16, 8); // RGBA8 color + DEPTH_COMPONENT24 renderbuffer, rounded 4B/pixel
  const target = new THREE.WebGLRenderTarget(1, 1, {
    depthBuffer: true,
    stencilBuffer: false,
  });
  const oldTarget = s.gl.getRenderTarget(),
    oldOrder = scalar.renderOrder,
    oldDepth = scalar.material.depthTest,
    oldBlend = scalar.material.blending;
  const pixels = new Uint8Array(4),
    visibility = installed.objects
      .slice(1)
      .map((o) => [o.mesh, o.mesh.visible] as const);
  const read = () => {
    s.gl.setRenderTarget(target);
    s.gl.render(s.scene, camera);
    s.gl.readRenderTargetPixels(target, 0, 0, 1, 1, pixels);
    return [...pixels];
  };
  try {
    for (const [o] of visibility) o.visible = false;
    scalar.renderOrder = 9999;
    scalar.material.depthTest = false;
    scalar.material.blending = THREE.NoBlending;
    scalar.material.uniforms.diagnostic.value = 1;
    const quantity = read(),
      mask = quantity[2],
      raw = quantity[0] * 256 + quantity[1] - 32768,
      value = mask
        ? null
        : raw * installed.d.components.t.scale! +
          installed.d.components.t.offset!;
    scalar.material.uniforms.diagnostic.value = 0;
    scalar.material.blending = THREE.NormalBlending;
    // Render known background through the actual Overview scene, keeping only
    // owned scalar visible; restore all visibility immediately after readback.
    const hidden = s.scene.children
        .filter((o) => o !== scalar)
        .map((o) => [o, o.visible] as const),
      background = s.scene.background;
    s.scene.background = new THREE.Color(0.1, 0.2, 0.3);
    for (const [o] of hidden) o.visible = false;
    let base: number[], color: number[];
    try {
      scalar.visible = false;
      base = read();
      scalar.visible = true;
      color = read();
    } finally {
      s.scene.background = background;
      for (const [o, v] of hidden) o.visible = v;
      scalar.visible = true;
    }
    const cpu = sampleGrid(
      installed.d,
      installed.values,
      installed.mask,
      sampleLatitude,
      sampleLongitude
    );
    return {
      latitude,
      longitude,
      sampleLatitude,
      sampleLongitude,
      pixel: { x, y, width, height },
      value,
      mask,
      quantity,
      cpu,
      base,
      color,
      quantizationStep: installed.d.components.t.scale,
      allocation: snapshot().allocation,
    };
  } finally {
    for (const [o, v] of visibility) o.visible = v;
    scalar.material.uniforms.diagnostic.value = 0;
    scalar.material.blending = oldBlend;
    scalar.material.depthTest = oldDepth;
    scalar.renderOrder = oldOrder;
    s.gl.setRenderTarget(oldTarget);
    target.dispose();
    release();
    s.invalidate();
  }
}
win.aviationProof = { install, dispose, sample, snapshot, look };
