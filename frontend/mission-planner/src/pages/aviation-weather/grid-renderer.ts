import * as THREE from 'three';
import type { GridLease } from '@/services/aviation-grid';
import type { GfsDrawing, GfsFlags } from './gfs-controller';
import {
  weatherKey,
  type WeatherBudget,
  type Reservation,
} from './weather-budget';
import { gridVertexShader, gridFragmentShader } from './grid-shader';
import { windSamples, windFrame } from './wind-barbs';
export function earthPoint(lat: number, lon: number, r = 2.012) {
  const a = (lat * Math.PI) / 180,
    b = (lon * Math.PI) / 180;
  return new THREE.Vector3(
    r * Math.cos(a) * Math.cos(b),
    r * Math.sin(a),
    -r * Math.cos(a) * Math.sin(b)
  );
}
export type NativeGridDrawing = GfsDrawing & {
  barbCount: number;
  barbSamples: Float64Array;
};
export function createGridDrawing(
  lease: GridLease,
  layers: GfsFlags,
  budget: WeatherBudget
): NativeGridDrawing {
  const object = new THREE.Group();
  object.name = 'Native GFS atmosphere';
  const resources: (() => void)[] = [];
  let retained: Reservation | undefined, temporary: Reservation | undefined;
  let samples: ReturnType<typeof windSamples> = [];
  try {
    temporary = budget.reserve(weatherKey('gfs-conversion'), {
      encoded: 0,
      decoded: 1024 ** 2,
      gpu: 0,
    });
    if (layers.winds) samples = windSamples(lease);
    const lineScalars = samples.reduce(
      (n, s) => n + (s.calm ? 16 * 6 : (1 + s.full + s.half) * 6),
      0
    );
    const flagScalars = samples.reduce((n, s) => n + s.flags * 9, 0);
    const rasterVertices = 128 * (64 - 1) * 6;
    const textureBytes = layers.temperature ? 259920 * 4 : 0;
    const rasterBytes = layers.temperature ? rasterVertices * 7 * 4 : 0;
    const windBytes = (lineScalars + flagScalars) * 4;
    const sampleBytes = samples.length * 9 * 8;
    const materialBytes =
      (layers.temperature ? 4096 : 0) + (layers.winds ? 4096 : 0);
    const bytes = {
      decoded:
        textureBytes + rasterBytes + windBytes + sampleBytes + materialBytes,
      gpu: textureBytes + rasterBytes + windBytes + materialBytes,
    };
    retained = budget.reserve(weatherKey('gfs-native'), {
      encoded: 0,
      ...bytes,
    });
    const barbSamples = new Float64Array(samples.length * 9);
    samples.forEach((s, i) =>
      barbSamples.set(
        [
          s.row,
          s.col,
          s.lat,
          s.lon,
          s.u,
          s.v,
          s.knots,
          s.fromEast,
          s.fromNorth,
        ],
        i * 9
      )
    );
    if (layers.temperature) {
      const packed = new Uint8Array(textureBytes);
      for (let i = 0; i < lease.t.length; i++) {
        packed[i * 4] = lease.t[i] & 255;
        packed[i * 4 + 1] = (lease.t[i] >> 8) & 255;
        packed[i * 4 + 2] = lease.mask[i];
        packed[i * 4 + 3] = 255;
      }
      const texture = new THREE.DataTexture(packed, 720, 361, THREE.RGBAFormat);
      texture.minFilter = texture.magFilter = THREE.NearestFilter;
      texture.generateMipmaps = false;
      texture.needsUpdate = true;
      resources.push(() => {
        texture.dispose();
        texture.image.data = new Uint8Array(0);
      });
      const positions = new Float32Array(rasterVertices * 3),
        planes = new Float32Array(rasterVertices * 4);
      let cursor = 0;
      const put = (lat: number, lon: number) => {
        earthPoint(lat, lon).toArray(positions, cursor);
        cursor += 3;
      };
      for (let row = 0; row < 64; row++)
        for (let col = 0; col < 128; col++) {
          const a = 90 - (row * 180) / 64,
            b = 90 - ((row + 1) * 180) / 64,
            x = -180 + (col * 360) / 128,
            y = -180 + ((col + 1) * 360) / 128;
          if (row > 0) {
            put(a, x);
            put(b, x);
            put(a, y);
          }
          if (row < 63) {
            put(a, y);
            put(b, x);
            put(b, y);
          }
        }
      const a = new THREE.Vector3(),
        b = new THREE.Vector3(),
        c = new THREE.Vector3();
      for (let i = 0; i < rasterVertices; i += 3) {
        a.fromArray(positions, i * 3);
        b.fromArray(positions, (i + 1) * 3);
        c.fromArray(positions, (i + 2) * 3);
        const n = b.sub(a).cross(c.sub(a)).normalize(),
          distance = n.dot(a);
        for (let j = 0; j < 3; j++) {
          const k = (i + j) * 4;
          planes[k] = n.x;
          planes[k + 1] = n.y;
          planes[k + 2] = n.z;
          planes[k + 3] = distance;
        }
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        'position',
        new THREE.BufferAttribute(positions, 3)
      );
      geometry.setAttribute(
        'trianglePlane',
        new THREE.BufferAttribute(planes, 4)
      );
      resources.push(() => {
        geometry.dispose();
        geometry.deleteAttribute('position');
        geometry.deleteAttribute('trianglePlane');
      });
      const component = lease.descriptor.grid.components[2];
      const material = new THREE.ShaderMaterial({
        uniforms: {
          packedGrid: { value: texture },
          size: { value: new THREE.Vector2(720, 361) },
          scale: { value: component.scale },
          offset: { value: component.offset },
          diagnostic: { value: 0 },
          inverseProjection: { value: new THREE.Matrix4() },
          cameraWorld: { value: new THREE.Matrix4() },
          eye: { value: new THREE.Vector3() },
          framebuffer: { value: new THREE.Vector2() },
        },
        vertexShader: gridVertexShader,
        fragmentShader: gridFragmentShader,
        transparent: true,
        depthWrite: false,
        toneMapped: false,
        side: THREE.DoubleSide,
      });
      resources.push(() => material.dispose());
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = 'GFS temperature';
      mesh.renderOrder = -101;
      mesh.raycast = () => {};
      mesh.onBeforeRender = (renderer, _scene, camera) => {
        material.uniforms.inverseProjection.value.copy(
          camera.projectionMatrixInverse
        );
        material.uniforms.cameraWorld.value.copy(camera.matrixWorld);
        material.uniforms.eye.value.setFromMatrixPosition(camera.matrixWorld);
        const target = renderer.getRenderTarget();
        if (target)
          material.uniforms.framebuffer.value.set(target.width, target.height);
        else renderer.getDrawingBufferSize(material.uniforms.framebuffer.value);
      };
      object.add(mesh);
    }
    if (layers.winds) {
      const lines = new Float32Array(lineScalars),
        flags = new Float32Array(flagScalars);
      let li = 0,
        fi = 0;
      for (const s of samples) {
        const base = earthPoint(s.lat, s.lon, 2.014),
          frame = windFrame(s.lat, s.lon, s.u, s.v),
          shaft = frame.shaft,
          side = base.clone().normalize().cross(shaft).normalize();
        const line = (a: THREE.Vector3, b: THREE.Vector3) => {
          a.toArray(lines, li);
          b.toArray(lines, li + 3);
          li += 6;
        };
        if (s.calm) {
          for (let i = 0; i < 16; i++) {
            const point = (angle: number) =>
              base
                .clone()
                .addScaledVector(frame.east, 0.008 * Math.cos(angle))
                .addScaledVector(frame.north, 0.008 * Math.sin(angle));
            line(
              point((i * 2 * Math.PI) / 16),
              point(((i + 1) * 2 * Math.PI) / 16)
            );
          }
          continue;
        }
        const marks = s.flags + s.full + s.half,
          length = Math.max(0.052, marks * 0.008 + 0.014);
        line(base, base.clone().addScaledVector(shaft, length));
        let pos = length;
        for (let i = 0; i < s.flags; i++) {
          const a = base.clone().addScaledVector(shaft, pos),
            b = a
              .clone()
              .addScaledVector(side, 0.02)
              .addScaledVector(shaft, -0.008),
            c = a.clone().addScaledVector(shaft, -0.008);
          a.toArray(flags, fi);
          b.toArray(flags, fi + 3);
          c.toArray(flags, fi + 6);
          fi += 9;
          pos -= 0.009;
        }
        for (let i = 0; i < s.full + s.half; i++) {
          const a = base.clone().addScaledVector(shaft, pos),
            b = a
              .clone()
              .addScaledVector(side, i < s.full ? 0.02 : 0.01)
              .addScaledVector(shaft, -0.006);
          line(a, b);
          pos -= 0.008;
        }
      }
      const add = (values: Float32Array, filled: boolean) => {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(values, 3));
        const material = filled
          ? new THREE.MeshBasicMaterial({
              color: 0xffffff,
              side: THREE.DoubleSide,
              depthWrite: false,
              toneMapped: false,
            })
          : new THREE.LineBasicMaterial({
              color: 0xffffff,
              depthWrite: false,
              toneMapped: false,
            });
        const mesh = filled
          ? new THREE.Mesh(geometry, material as THREE.MeshBasicMaterial)
          : new THREE.LineSegments(
              geometry,
              material as THREE.LineBasicMaterial
            );
        mesh.name = filled ? 'GFS 50 kt pennants' : 'GFS wind FROM barbs';
        mesh.renderOrder = 19;
        mesh.raycast = () => {};
        object.add(mesh);
        resources.push(() => {
          geometry.dispose();
          geometry.deleteAttribute('position');
          material.dispose();
        });
      };
      add(lines, false);
      add(flags, true);
    }
    object.userData.gfs = {
      grid: {
        descriptor: lease.descriptor,
        u: lease.u,
        v: lease.v,
        t: lease.t,
        mask: lease.mask,
      },
      barbSamples,
      bytes,
      budget: () => budget.snapshot(),
    };
    temporary.release();
    temporary = undefined;
    let owned = true;
    return {
      object,
      bytes,
      barbCount: samples.length,
      barbSamples,
      dispose() {
        if (!owned) return;
        owned = false;
        object.clear();
        object.userData = {};
        resources.forEach((dispose) => dispose());
        retained?.release();
      },
    };
  } catch (error) {
    resources.forEach((dispose) => dispose());
    object.clear();
    retained?.release();
    temporary?.release();
    throw error;
  }
}
