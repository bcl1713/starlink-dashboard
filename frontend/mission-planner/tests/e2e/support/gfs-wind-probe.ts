import type { Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type {
  Mesh,
  ShaderMaterial,
  Object3D,
  Intersection,
  LineSegments,
  Blending,
} from 'three';

export type GeoSample = { latitude: number; longitude: number };
type NativeWindow = Window & {
  __gfsOwnedBytes?: () => { decoded: number; gpu: number };
  __overviewEvidenceRoots?: {
    containerInfo?: { getState?: () => RootState };
  }[];
};
export async function windSnapshot(page: Page) {
  return page.evaluate(() => {
    const state = (window as NativeWindow).__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    if (!state) return null;
    const object = state.scene.getObjectByName('Native GFS atmosphere');
    if (!object?.userData.gfs)
      return {
        present: false,
        calls: state.gl.info.render.calls,
        ownedBytes: (window as NativeWindow).__gfsOwnedBytes?.(),
      };
    const g = object.userData.gfs;
    const bytes = g.bytes;
    (window as NativeWindow).__gfsOwnedBytes = () => ({ ...bytes });
    const lines = state.scene.getObjectByName('GFS wind particles') as
      | LineSegments
      | undefined;
    const particles = lines?.userData.windParticles;
    return {
      present: true,
      mode: g.mode,
      instance: g.grid.descriptor.instance_id,
      temperature: !!state.scene.getObjectByName('GFS temperature'),
      wind: !!state.scene.getObjectByName('GFS wind speed'),
      particleCount: particles?.count ?? 0,
      vertices: lines?.geometry.drawRange.count ?? 0,
      positions: Array.from(
        particles?.positions.slice(0, 72) ?? []
      ) as number[],
      points: Array.from(particles?.points.slice(0, 12) ?? []) as number[],
      finite: !particles || particles.positions.every(Number.isFinite),
      depthTest: lines ? (lines.material as ShaderMaterial).depthTest : null,
      depthWrite: lines ? (lines.material as ShaderMaterial).depthWrite : null,
      bulletins: [
        'Native METAR / SPECI observations',
        'Native TAF terminal forecasts',
        'Native international SIGMET advisories',
      ].map((name) => !!state.scene.getObjectByName(name)),
      calls: state.gl.info.render.calls,
      geometryCount: state.gl.info.memory.geometries,
      textureCount: state.gl.info.memory.textures,
      renderer: (() => {
        const gl = state.gl.getContext(),
          ext = gl.getExtension('WEBGL_debug_renderer_info');
        return String(
          gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER)
        );
      })(),
      vertical: g.grid.descriptor.vertical,
      lead: g.grid.descriptor.lead_seconds,
      valid: g.grid.descriptor.valid_at_ms,
      budget: g.budget(),
      bytes: { ...g.bytes },
    };
  });
}

// Uses the admitted production material, packed textures and framebuffer. The
// actual triangle hit accounts for pixel rounding and Overview's view offset.
export async function windReadbacks(page: Page, coordinates: GeoSample[]) {
  return page.evaluate((coordinates) => {
    const state = (window as NativeWindow).__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    if (!state) throw Error('Native renderer missing');
    const object = state.scene.getObjectByName('Native GFS atmosphere');
    if (!object?.userData.gfs) throw Error('Native grid missing');
    const grid = object.userData.gfs.grid;
    const wind = object.userData.gfs.mode === 'winds';
    const mesh = state.scene.getObjectByName(
      wind ? 'GFS wind speed' : 'GFS temperature'
    ) as Mesh<import('three').BufferGeometry, ShaderMaterial>;
    const material = mesh.material;
    const controls = state.controls as unknown as {
      setLookAt: (...v: (number | boolean)[]) => void;
      update: (n: number) => void;
      getTarget: (out: import('three').Vector3) => void;
    };
    const eye = state.camera.position.clone(),
      target = eye.clone();
    controls.getTarget(target);
    const visibility: { node: Object3D; visible: boolean }[] = [];
    const diagnostic = material.uniforms.diagnostic.value,
      blending = material.blending;
    state.scene.traverse((node) => {
      if (['Mesh', 'LineSegments', 'Points'].includes(node.type)) {
        visibility.push({ node, visible: node.visible });
        node.visible = node === mesh;
      }
    });
    const gl = state.gl.getContext();
    const out = [];
    const stops = [0, 25, 50, 75, 100, 125, 150];
    const colors = [
      [29, 78, 216],
      [6, 182, 212],
      [34, 197, 94],
      [234, 179, 8],
      [249, 115, 22],
      [239, 68, 68],
      [168, 85, 247],
    ];
    try {
      for (const geo of coordinates) {
        const lat = (geo.latitude * Math.PI) / 180,
          lon = (geo.longitude * Math.PI) / 180;
        controls.setLookAt(
          3 * Math.cos(lat) * Math.cos(lon),
          3 * Math.sin(lat),
          -3 * Math.cos(lat) * Math.sin(lon),
          0,
          0,
          0,
          false
        );
        controls.update(0);
        state.camera.updateMatrixWorld();
        const landmark = eye
          .clone()
          .set(
            2.012 * Math.cos(lat) * Math.cos(lon),
            2.012 * Math.sin(lat),
            -2.012 * Math.cos(lat) * Math.sin(lon)
          )
          .project(state.camera);
        const x = Math.floor((landmark.x / 2 + 0.5) * gl.drawingBufferWidth),
          y = Math.floor((landmark.y / 2 + 0.5) * gl.drawingBufferHeight);
        state.raycaster.setFromCamera(
          material.uniforms.size.value
            .clone()
            .set(
              ((x + 0.5) / gl.drawingBufferWidth) * 2 - 1,
              ((y + 0.5) / gl.drawingBufferHeight) * 2 - 1
            ),
          state.camera
        );
        const hits: Intersection[] = [];
        Object.getPrototypeOf(mesh).raycast.call(mesh, state.raycaster, hits);
        hits.sort((a, b) => a.distance - b.distance);
        if (!hits.length) throw Error('No native triangle intersection');
        const point = hits[0].point.clone().normalize();
        const latitude = (Math.asin(point.y) * 180) / Math.PI,
          longitude = (Math.atan2(-point.z, point.x) * 180) / Math.PI;
        const qx = ((((longitude + 180) % 360) + 360) % 360) * 2,
          qy = Math.max(0, Math.min(360, (90 - latitude) * 2));
        const col = Math.floor(qx),
          row = Math.floor(qy),
          fx = qx - col,
          fy = qy - row;
        const contributors = [
          [row * 720 + col, (1 - fx) * (1 - fy)],
          [row * 720 + ((col + 1) % 720), fx * (1 - fy)],
          [Math.min(360, row + 1) * 720 + col, (1 - fx) * fy],
          [Math.min(360, row + 1) * 720 + ((col + 1) % 720), fx * fy],
        ];
        const read = (mode: number, blend: Blending = 0) => {
          material.uniforms.diagnostic.value = mode;
          material.blending = blend;
          state.gl.render(state.scene, state.camera);
          const bytes = new Uint8Array(4);
          gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, bytes);
          return [...bytes];
        };
        const mask = Math.max(
          ...contributors.filter(([, w]) => w > 0).map(([i]) => grid.mask[i])
        );
        const component = (name: 'u' | 'v' | 't', mode: number) => {
          const cpu =
            contributors.reduce((sum, [i, w]) => sum + grid[name][i] * w, 0) *
              0.01 +
            (name === 't' ? 273.15 : 0);
          const bytes = read(mode);
          const gpu =
            (bytes[0] * 256 + bytes[1] - 32768) * 0.01 +
            (name === 't' ? 273.15 : 0);
          return {
            cpu,
            gpu,
            error: Math.abs(cpu - gpu),
            mask,
            gpuMask: bytes[2],
          };
        };
        const node =
          Math.round((90 - geo.latitude) * 2) * 720 +
          (Math.round((geo.longitude + 180) * 2) % 720);
        const base = {
          ...geo,
          sampledLatitude: latitude,
          sampledLongitude: longitude,
          node: {
            u: grid.u[node] * 0.01,
            v: grid.v[node] * 0.01,
            t: grid.t[node] * 0.01 + 273.15,
            mask: grid.mask[node],
          },
        };
        if (wind) {
          const u = component('u', 1),
            v = component('v', 2),
            cpuKnots = Math.hypot(u.cpu, v.cpu) * 1.9438444924406;
          const speed = read(4),
            gpuKnots = (speed[0] * 65536 + speed[1] * 256 + speed[2]) / 100;
          const rgba = read(5);
          const k = Math.max(0, Math.min(150, cpuKnots)),
            lo = Math.min(5, Math.floor(k / 25)),
            f = (k - stops[lo]) / 25;
          const expectedColor = colors[lo].map(
            (c, i) => c + (colors[lo + 1][i] - c) * f
          );
          const productionRGBA = read(0, blending);
          mesh.visible = false;
          const hiddenRGBA = read(0, blending);
          mesh.visible = true;
          out.push({
            ...base,
            u,
            v,
            mask,
            knots: gpuKnots,
            cpuKnots,
            speedMask: speed[3],
            rgba,
            expectedColor,
            productionRGBA,
            hiddenRGBA,
            maskedTransparent: productionRGBA.every(
              (c, i) => c === hiddenRGBA[i]
            ),
          });
        } else {
          const t = component('t', 3),
            productionRGBA = read(0, blending);
          mesh.visible = false;
          const hiddenRGBA = read(0, blending);
          mesh.visible = true;
          out.push({
            ...base,
            t,
            mask,
            productionRGBA,
            hiddenRGBA,
            maskedTransparent: productionRGBA.every(
              (c, i) => c === hiddenRGBA[i]
            ),
          });
        }
      }
    } finally {
      material.uniforms.diagnostic.value = diagnostic;
      material.blending = blending;
      visibility.forEach(({ node, visible }) => {
        node.visible = visible;
      });
      controls.setLookAt(
        eye.x,
        eye.y,
        eye.z,
        target.x,
        target.y,
        target.z,
        false
      );
      controls.update(0);
      state.gl.render(state.scene, state.camera);
    }
    return out;
  }, coordinates);
}

// Compare actual particle framebuffer pixels with the owner hidden. Restrict
// far-side controls to pixels that have no near-side trail in the same patch.
export async function windTrailPixels(page: Page) {
  return page.evaluate(() => {
    const state = (window as NativeWindow).__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    if (!state) throw Error('Missing native renderer');
    const lines = state.scene.getObjectByName(
      'GFS wind particles'
    ) as LineSegments;
    if (!lines) throw Error('Missing particle owner');
    const gl = state.gl.getContext(),
      width = gl.drawingBufferWidth,
      height = gl.drawingBufferHeight;
    const visible = lines.visible;
    try {
      const read = () => {
        state.gl.render(state.scene, state.camera);
        const pixels = new Uint8Array(width * height * 4);
        gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        return pixels;
      };
      lines.visible = true;
      const withTrails = read();
      lines.visible = false;
      const withoutTrails = read();
      const attr = lines.geometry.getAttribute('position');
      const near: number[][] = [],
        far: number[][] = [];
      for (let i = 0; i < lines.geometry.drawRange.count; i++) {
        const point = state.camera.position
            .clone()
            .fromBufferAttribute(attr, i),
          facing = point.dot(state.camera.position);
        const projected = point.clone().project(state.camera);
        const x = Math.floor((projected.x / 2 + 0.5) * width),
          y = Math.floor((projected.y / 2 + 0.5) * height);
        if (x < 2 || x >= width - 2 || y < 2 || y >= height - 2) continue;
        if (facing >= 0) near.push([x, y]);
        else if (facing < 0) far.push([x, y]);
      }
      const differs = (x: number, y: number) => {
        for (let dy = -1; dy <= 1; dy++)
          for (let dx = -1; dx <= 1; dx++) {
            const index = ((y + dy) * width + x + dx) * 4;
            for (let c = 0; c < 3; c++)
              if (
                Math.abs(withTrails[index + c] - withoutTrails[index + c]) > 2
              )
                return true;
          }
        return false;
      };
      const frontChanged = near.filter(([x, y]) => differs(x, y)).length;
      const farControls = far
        .filter(
          ([x, y]) =>
            !near.some(([a, b]) => Math.abs(x - a) < 8 && Math.abs(y - b) < 8)
        )
        .slice(0, 100);
      return {
        frontChanged,
        farControls: farControls.length,
        farChanged: farControls.filter(([x, y]) => differs(x, y)).length,
      };
    } finally {
      lines.visible = visible;
      state.gl.render(state.scene, state.camera);
    }
  });
}

export async function windDirection(page: Page) {
  const snapshot = await windSnapshot(page);
  const line = snapshot?.positions;
  if (!line || line.length < 6) throw Error('No native trail');
  const midpoint = [
    (line[0] + line[3]) / 2,
    (line[1] + line[4]) / 2,
    (line[2] + line[5]) / 2,
  ];
  const length = Math.hypot(...midpoint),
    lat = Math.asin(midpoint[1] / length),
    lon = Math.atan2(-midpoint[2], midpoint[0]);
  const [sample] = await windReadbacks(page, [
    { latitude: (lat * 180) / Math.PI, longitude: (lon * 180) / Math.PI },
  ]);
  if (!('u' in sample) || sample.mask) throw Error('No valid direction sample');
  const east = [-Math.sin(lon), 0, -Math.cos(lon)],
    north = [
      -Math.sin(lat) * Math.cos(lon),
      Math.cos(lat),
      Math.sin(lat) * Math.sin(lon),
    ];
  const delta = [line[3] - line[0], line[4] - line[1], line[5] - line[2]],
    distance = Math.hypot(...delta),
    speed = Math.hypot(sample.u.cpu, sample.v.cpu);
  if (!distance || !speed) throw Error('No nonzero direction control');
  const expected = east.map(
    (value, i) => (value * sample.u.cpu + north[i] * sample.v.cpu) / speed
  );
  return {
    alignment: delta.reduce(
      (sum, value, i) => sum + (value / distance) * expected[i],
      0
    ),
    sample,
    line: line.slice(0, 6),
  };
}
