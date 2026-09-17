import { vi } from 'vitest';

const renderedFlow = vi.hoisted(() => ({
  frame: undefined as undefined | ((state: unknown, delta: number) => void),
  particles: [] as unknown[],
}));

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useEffect: (effect: () => void | (() => void)) => {
      effect();
    },
    useMemo: <Value,>(create: () => Value) => create(),
    useState: <Value,>(initial: Value | (() => Value)) => [
      typeof initial === 'function' ? (initial as () => Value)() : initial,
      vi.fn(),
    ],
  };
});

vi.mock('@react-three/drei', () => ({ Line: () => null }));

vi.mock('@react-three/fiber', () => ({
  useFrame: (frame: (state: unknown, delta: number) => void) => {
    renderedFlow.frame = frame;
  },
}));

vi.mock('./overview-animated-flow-line-rendering', async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import('./overview-animated-flow-line-rendering')
    >();
  return {
    ...actual,
    writeFlowParticles: vi.fn(
      (_resources, _points, particles: readonly unknown[]) => {
        renderedFlow.particles = [...particles];
      }
    ),
  };
});

import { describe, expect, it } from 'vitest';
import { AnimatedFlowLine } from './AnimatedFlowLine';

describe('AnimatedFlowLine', () => {
  it('renders reverse particles from a reverse-only mounted configuration', () => {
    AnimatedFlowLine({
      points: [
        [0, 0, 0],
        [1, 0, 0],
      ],
      reverse: {
        enabled: true,
        rate: 2,
        speed: 1,
        color: '#c084fc',
        size: 6,
        brightness: 1,
        maxParticles: 2,
      },
      random: () => 0.5,
    });

    renderedFlow.frame?.({}, 0.5);

    expect(renderedFlow.particles).toHaveLength(1);
    expect(renderedFlow.particles[0]).toMatchObject({
      direction: 'reverse',
      color: '#c084fc',
    });
  });
});
