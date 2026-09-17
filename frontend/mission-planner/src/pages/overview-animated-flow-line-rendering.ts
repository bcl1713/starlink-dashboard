import * as THREE from 'three';

export type FlowPoint = readonly [number, number, number];
export type FlowDirection = 'forward' | 'reverse';
export type FlowParticleState = 'traveling' | 'burst';

export interface FlowFailureConfig {
  probability: number;
  burstCount?: number;
  duration?: number;
}

export interface FlowEmitterConfig {
  enabled: boolean;
  rate: number;
  speed: number;
  color: string;
  size: number;
  brightness: number;
  maxParticles: number;
  failure?: FlowFailureConfig;
}

export interface FlowParticle {
  direction: FlowDirection;
  progress: number;
  speed: number;
  color: string;
  size: number;
  brightness: number;
  state: FlowParticleState;
  failureAt: number | null;
  burstCount: number;
  burstDuration: number;
  burstAge: number;
}

export interface FlowParticlePoolOptions {
  points: readonly FlowPoint[];
  forward?: FlowEmitterConfig;
  reverse?: FlowEmitterConfig;
  random?: () => number;
}

export interface AnimatedFlowResources {
  geometry: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
  points: THREE.Points;
}

const EMPTY_EMITTER: FlowEmitterConfig = {
  enabled: false,
  rate: 0,
  speed: 0,
  color: '#ffffff',
  size: 1,
  brightness: 0,
  maxParticles: 0,
};

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function pathSegments(points: readonly FlowPoint[]) {
  return points.slice(1).map((point, index) => {
    const start = points[index];
    const length = Math.hypot(
      point[0] - start[0],
      point[1] - start[1],
      point[2] - start[2]
    );
    return { start, end: point, length };
  });
}

export function interpolateFlowPath(
  points: readonly FlowPoint[],
  progress: number
): [number, number, number] | null {
  if (points.length === 0) return null;
  if (points.length === 1) return [...points[0]];

  const segments = pathSegments(points);
  const totalLength = segments.reduce(
    (total, segment) => total + segment.length,
    0
  );
  if (totalLength === 0) return [...points[0]];

  let distance = clamp(progress, 0, 1) * totalLength;
  for (const segment of segments) {
    if (distance <= segment.length || segment === segments.at(-1)) {
      const t = segment.length === 0 ? 0 : distance / segment.length;
      return [
        THREE.MathUtils.lerp(segment.start[0], segment.end[0], t),
        THREE.MathUtils.lerp(segment.start[1], segment.end[1], t),
        THREE.MathUtils.lerp(segment.start[2], segment.end[2], t),
      ];
    }
    distance -= segment.length;
  }

  return [...points.at(-1)!];
}

export class FlowParticlePool {
  private readonly points: readonly FlowPoint[];
  private readonly random: () => number;
  private readonly particles: FlowParticle[] = [];
  private readonly recycled: FlowParticle[] = [];
  private forward: FlowEmitterConfig;
  private reverse: FlowEmitterConfig;
  private forwardRemainder = 0;
  private reverseRemainder = 0;

  constructor({
    points,
    forward = EMPTY_EMITTER,
    reverse = EMPTY_EMITTER,
    random = Math.random,
  }: FlowParticlePoolOptions) {
    this.points = points;
    this.forward = forward;
    this.reverse = reverse;
    this.random = random;
  }

  configure(forward: FlowEmitterConfig, reverse = this.reverse): void {
    this.forward = forward;
    this.reverse = reverse;
  }

  snapshot(): readonly FlowParticle[] {
    return this.particles;
  }

  update(deltaSeconds: number): void {
    if (this.points.length < 2 || !Number.isFinite(deltaSeconds)) return;

    for (const particle of this.particles) {
      if (particle.state === 'burst') {
        particle.burstAge += deltaSeconds;
        continue;
      }
      particle.progress +=
        particle.direction === 'forward'
          ? particle.speed * deltaSeconds
          : -particle.speed * deltaSeconds;
      if (
        particle.failureAt !== null &&
        (particle.direction === 'forward'
          ? particle.progress >= particle.failureAt
          : particle.progress <= particle.failureAt)
      ) {
        particle.progress = particle.failureAt;
        particle.state = 'burst';
      }
    }

    for (let index = this.particles.length - 1; index >= 0; index -= 1) {
      const particle = this.particles[index];
      if (
        (particle.state === 'burst' &&
          particle.burstAge >= particle.burstDuration) ||
        (particle.state === 'traveling' &&
          (particle.progress < 0 || particle.progress > 1))
      ) {
        this.recycled.push(particle);
        this.particles.splice(index, 1);
      }
    }

    this.forwardRemainder = this.emit(
      this.forward,
      'forward',
      this.forwardRemainder + deltaSeconds * this.forward.rate
    );
    this.reverseRemainder = this.emit(
      this.reverse,
      'reverse',
      this.reverseRemainder + deltaSeconds * this.reverse.rate
    );
  }

  private emit(
    emitter: FlowEmitterConfig,
    direction: FlowDirection,
    requested: number
  ): number {
    if (!emitter.enabled || emitter.maxParticles <= 0 || emitter.rate <= 0) {
      return 0;
    }
    const existing = this.particles.filter(
      (particle) => particle.direction === direction
    ).length;
    let available = Math.max(0, emitter.maxParticles - existing);
    let remainder = requested;
    while (remainder >= 1 && available > 0) {
      const failed =
        emitter.failure !== undefined &&
        this.random() < emitter.failure.probability;
      const failureProgress = 0.25 + this.random() * 0.5;
      const particle = this.recycled.pop() ?? ({} as FlowParticle);
      Object.assign(particle, {
        direction,
        progress: direction === 'forward' ? 0 : 1,
        speed: emitter.speed,
        color: emitter.color,
        size: emitter.size,
        brightness: emitter.brightness,
        state: 'traveling',
        failureAt: failed ? failureProgress : null,
        burstCount: emitter.failure?.burstCount ?? 4,
        burstDuration: emitter.failure?.duration ?? 0.35,
        burstAge: 0,
      });
      this.particles.push(particle);
      remainder -= 1;
      available -= 1;
    }
    return Math.min(remainder, 1);
  }
}

export function createAnimatedFlowResources(
  capacity: number
): AnimatedFlowResources {
  const safeCapacity = Math.max(1, Math.floor(capacity));
  const geometry = new THREE.BufferGeometry();
  for (const [name, itemSize] of [
    ['position', 3],
    ['color', 3],
    ['size', 1],
    ['brightness', 1],
  ] as const) {
    geometry.setAttribute(
      name,
      new THREE.BufferAttribute(
        new Float32Array(safeCapacity * itemSize),
        itemSize
      ).setUsage(THREE.DynamicDrawUsage)
    );
  }
  geometry.setDrawRange(0, 0);
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute float size;
      attribute float brightness;
      varying vec3 vColor;
      varying float vBrightness;
      void main() {
        vColor = color;
        vBrightness = brightness;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = size * (240.0 / max(0.1, -mvPosition.z));
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vBrightness;
      void main() {
        float distanceFromCenter = length(gl_PointCoord - 0.5) * 2.0;
        float alpha = smoothstep(1.0, 0.0, distanceFromCenter);
        gl_FragColor = vec4(vColor * vBrightness, alpha * vBrightness);
      }
    `,
  });
  const points = new THREE.Points(geometry, material);
  points.castShadow = false;
  points.receiveShadow = false;
  return { geometry, material, points };
}

export function writeFlowParticles(
  resources: AnimatedFlowResources,
  points: readonly FlowPoint[],
  particles: readonly FlowParticle[]
): void {
  const positions = resources.geometry.getAttribute(
    'position'
  ) as THREE.BufferAttribute;
  const colors = resources.geometry.getAttribute(
    'color'
  ) as THREE.BufferAttribute;
  const sizes = resources.geometry.getAttribute(
    'size'
  ) as THREE.BufferAttribute;
  const brightness = resources.geometry.getAttribute(
    'brightness'
  ) as THREE.BufferAttribute;
  let index = 0;
  for (const particle of particles) {
    const origin = interpolateFlowPath(points, particle.progress);
    if (!origin) continue;
    const color = new THREE.Color(particle.color);
    const count = particle.state === 'burst' ? particle.burstCount : 1;
    for (
      let burstIndex = 0;
      burstIndex < count && index < positions.count;
      burstIndex += 1
    ) {
      const burstScale =
        particle.state === 'burst' ? particle.burstAge * 0.25 : 0;
      const angle = (Math.PI * 2 * burstIndex) / count;
      positions.setXYZ(
        index,
        origin[0] + Math.cos(angle) * burstScale,
        origin[1] + Math.sin(angle) * burstScale,
        origin[2]
      );
      colors.setXYZ(index, color.r, color.g, color.b);
      sizes.setX(index, particle.size * (particle.state === 'burst' ? 1.5 : 1));
      brightness.setX(index, particle.brightness);
      index += 1;
    }
  }
  positions.needsUpdate = true;
  colors.needsUpdate = true;
  sizes.needsUpdate = true;
  brightness.needsUpdate = true;
  resources.geometry.setDrawRange(0, index);
}

export function disposeAnimatedFlowResources(
  resources: AnimatedFlowResources
): void {
  resources.geometry.dispose();
  resources.material.dispose();
}
