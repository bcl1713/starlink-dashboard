import * as THREE from 'three';

export type FlowPoint = readonly [number, number, number];
export type FlowDirection = 'forward' | 'reverse';
export type FlowParticleState = 'traveling' | 'burst';

export interface FlowFailureConfig {
  probability: number;
  duration?: number;
  color?: string;
  minProgress?: number;
  maxProgress?: number;
}

export interface FlowEmitterConfig {
  enabled: boolean;
  rate: number;
  /** Linear travel speed in scene units per second. */
  speed: number;
  color: string;
  size: number;
  brightness: number;
  maxParticles: number;
  /**
   * Optional world-space diameter cap. Packets remain `size` CSS pixels up
   * close, but shrink naturally with distance once this cap becomes smaller
   * than the requested screen-space size.
   */
  maxWorldSize?: number;
  failure?: FlowFailureConfig;
}

export interface FlowParticle {
  direction: FlowDirection;
  progress: number;
  /** Linear travel speed in scene units per second, snapshotted at emission. */
  speed: number;
  color: string;
  size: number;
  brightness: number;
  maxWorldSize: number;
  failureColor: string;
  state: FlowParticleState;
  failureAt: number | null;
  burstDuration: number;
  burstAge: number;
}

export interface FlowParticlePoolOptions {
  forward?: FlowEmitterConfig;
  reverse?: FlowEmitterConfig;
  random?: () => number;
}

export interface PreparedFlowPath {
  points: readonly FlowPoint[];
  cumulativeLengths: Float32Array;
  totalLength: number;
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

const scratchColor = new THREE.Color();

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function prepareFlowPath(
  points: readonly FlowPoint[]
): PreparedFlowPath {
  const cumulativeLengths = new Float32Array(points.length);
  let totalLength = 0;

  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    totalLength += Math.hypot(
      end[0] - start[0],
      end[1] - start[1],
      end[2] - start[2]
    );
    cumulativeLengths[index] = totalLength;
  }

  return { points, cumulativeLengths, totalLength };
}

export function interpolatePreparedFlowPath(
  path: PreparedFlowPath,
  progress: number
): [number, number, number] | null {
  const { points, cumulativeLengths, totalLength } = path;
  if (points.length === 0) return null;
  if (points.length === 1 || totalLength === 0) return [...points[0]];

  const targetDistance = clamp(progress, 0, 1) * totalLength;
  let endIndex = 1;

  while (
    endIndex < cumulativeLengths.length - 1 &&
    targetDistance > cumulativeLengths[endIndex]
  ) {
    endIndex += 1;
  }

  const startIndex = endIndex - 1;
  const segmentStart = cumulativeLengths[startIndex];
  const segmentEnd = cumulativeLengths[endIndex];
  const segmentLength = segmentEnd - segmentStart;
  const t =
    segmentLength === 0 ? 0 : (targetDistance - segmentStart) / segmentLength;
  const start = points[startIndex];
  const end = points[endIndex];

  return [
    THREE.MathUtils.lerp(start[0], end[0], t),
    THREE.MathUtils.lerp(start[1], end[1], t),
    THREE.MathUtils.lerp(start[2], end[2], t),
  ];
}

export function interpolateFlowPath(
  points: readonly FlowPoint[],
  progress: number
): [number, number, number] | null {
  return interpolatePreparedFlowPath(prepareFlowPath(points), progress);
}

export class FlowParticlePool {
  private readonly random: () => number;
  private readonly particles: FlowParticle[] = [];
  private readonly recycled: FlowParticle[] = [];
  private forward: FlowEmitterConfig;
  private reverse: FlowEmitterConfig;
  private forwardRemainder = 0;
  private reverseRemainder = 0;

  constructor({
    forward = EMPTY_EMITTER,
    reverse = EMPTY_EMITTER,
    random = Math.random,
  }: FlowParticlePoolOptions = {}) {
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

  update(deltaSeconds: number, pathLength: number): void {
    if (
      !Number.isFinite(deltaSeconds) ||
      deltaSeconds <= 0 ||
      !Number.isFinite(pathLength) ||
      pathLength <= 0
    ) {
      return;
    }

    for (const particle of this.particles) {
      if (particle.state === 'burst') {
        particle.burstAge += deltaSeconds;
        continue;
      }

      const progressDelta = (particle.speed * deltaSeconds) / pathLength;
      particle.progress +=
        particle.direction === 'forward' ? progressDelta : -progressDelta;

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
      const expiredBurst =
        particle.state === 'burst' &&
        particle.burstAge >= particle.burstDuration;
      const completedTravel =
        particle.state === 'traveling' &&
        (particle.progress < 0 || particle.progress > 1);

      if (expiredBurst || completedTravel) {
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
      const failure = emitter.failure;
      const failed =
        failure !== undefined && this.random() < clamp(failure.probability, 0, 1);
      const minProgress = clamp(failure?.minProgress ?? 0.15, 0, 1);
      const maxProgress = clamp(
        failure?.maxProgress ?? 0.85,
        minProgress,
        1
      );
      const failureProgress = THREE.MathUtils.lerp(
        minProgress,
        maxProgress,
        this.random()
      );
      const particle = this.recycled.pop() ?? ({} as FlowParticle);

      Object.assign(particle, {
        direction,
        progress: direction === 'forward' ? 0 : 1,
        speed: emitter.speed,
        color: emitter.color,
        size: emitter.size,
        brightness: emitter.brightness,
        maxWorldSize: Math.max(0, emitter.maxWorldSize ?? 0),
        failureColor: failure?.color ?? '#ff304f',
        state: 'traveling',
        failureAt: failed ? failureProgress : null,
        burstDuration: failure?.duration ?? 0.42,
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
    ['maxWorldSize', 1],
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
    uniforms: {
      uPixelRatio: { value: 1 },
      uViewportHeightPixels: { value: 1 },
      uDepthBias: { value: 0.00001 },
    },
    transparent: true,
    depthWrite: false,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
    vertexShader: `
      uniform float uPixelRatio;
      uniform float uViewportHeightPixels;
      uniform float uDepthBias;
      attribute float size;
      attribute float brightness;
      attribute float maxWorldSize;
      varying vec3 vColor;
      varying float vBrightness;

      void main() {
        vColor = color;
        vBrightness = brightness;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        float requestedSize = size * uPixelRatio;
        float renderedSize = requestedSize;

        if (maxWorldSize > 0.0) {
          float viewDistance = max(0.0001, -mvPosition.z);
          float projectedWorldSize =
            maxWorldSize * projectionMatrix[1][1] * uViewportHeightPixels *
            0.5 / viewDistance;
          renderedSize = min(requestedSize, projectedWorldSize);
        }

        gl_PointSize = max(1.0, renderedSize);
        gl_Position = projectionMatrix * mvPosition;
        gl_Position.z -= uDepthBias * gl_Position.w;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vBrightness;

      void main() {
        vec2 point = gl_PointCoord - vec2(0.5);
        float distanceFromCenter = length(point);
        if (distanceFromCenter > 0.5) discard;

        float alpha = 1.0 - smoothstep(0.0, 0.5, distanceFromCenter);
        alpha = pow(alpha, 1.5);
        float hot = 1.0 - smoothstep(0.0, 0.18, distanceFromCenter);
        vec3 color = mix(vColor, vec3(1.0), hot);
        gl_FragColor = vec4(color * vBrightness, alpha);
      }
    `,
  });
  const points = new THREE.Points(geometry, material);
  points.castShadow = false;
  points.receiveShadow = false;
  points.frustumCulled = false;
  return { geometry, material, points };
}

export function writeFlowParticles(
  resources: AnimatedFlowResources,
  path: PreparedFlowPath,
  particles: readonly FlowParticle[]
): void {
  const positions = resources.geometry.getAttribute(
    'position'
  ) as THREE.BufferAttribute;
  const colors = resources.geometry.getAttribute(
    'color'
  ) as THREE.BufferAttribute;
  const sizes = resources.geometry.getAttribute('size') as THREE.BufferAttribute;
  const brightness = resources.geometry.getAttribute(
    'brightness'
  ) as THREE.BufferAttribute;
  const maxWorldSizes = resources.geometry.getAttribute(
    'maxWorldSize'
  ) as THREE.BufferAttribute;
  let index = 0;

  for (const particle of particles) {
    if (index >= positions.count) break;
    const origin = interpolatePreparedFlowPath(path, particle.progress);
    if (!origin) continue;

    const burstLife =
      particle.state === 'burst'
        ? clamp(particle.burstAge / particle.burstDuration, 0, 1)
        : 0;
    const burstScale =
      particle.state === 'burst' ? 2.4 + burstLife * 3.6 : 1;
    const particleSize = particle.size * burstScale;
    const particleBrightness =
      particle.state === 'burst'
        ? THREE.MathUtils.lerp(5.2, 0, burstLife)
        : particle.brightness;

    scratchColor.set(
      particle.state === 'burst' ? particle.failureColor : particle.color
    );
    positions.setXYZ(index, origin[0], origin[1], origin[2]);
    colors.setXYZ(index, scratchColor.r, scratchColor.g, scratchColor.b);
    sizes.setX(index, particleSize);
    brightness.setX(index, particleBrightness);
    maxWorldSizes.setX(index, particle.maxWorldSize * burstScale);
    index += 1;
  }

  positions.needsUpdate = true;
  colors.needsUpdate = true;
  sizes.needsUpdate = true;
  brightness.needsUpdate = true;
  maxWorldSizes.needsUpdate = true;
  resources.geometry.setDrawRange(0, index);
}

export function disposeAnimatedFlowResources(
  resources: AnimatedFlowResources
): void {
  resources.geometry.dispose();
  resources.material.dispose();
}
