/** @vitest-environment jsdom */

import { act, cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const renderedFlow = vi.hoisted(() => ({
  frame: undefined as undefined | ((state: unknown, delta: number) => void),
  particles: [] as unknown[],
}));

vi.mock('@react-three/drei', async () => {
  const React = await import('react');
  return {
    Line: () => React.createElement('div', { 'data-testid': 'flow-line' }),
  };
});

vi.mock('@react-three/fiber', async () => {
  const React = await import('react');
  return {
    useFrame: (frame: (state: unknown, delta: number) => void) => {
      React.useEffect(() => {
        renderedFlow.frame = frame;
        return () => {
          if (renderedFlow.frame === frame) renderedFlow.frame = undefined;
        };
      }, [frame]);
    },
  };
});

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

import { AnimatedFlowLine } from './AnimatedFlowLine';

afterEach(() => {
  cleanup();
  renderedFlow.frame = undefined;
  renderedFlow.particles = [];
});

describe('AnimatedFlowLine', () => {
  it('emits only reverse particles after a reverse-only configuration mounts', () => {
    const { getAllByTestId } = render(
      <AnimatedFlowLine
        points={[
          [0, 0, 0],
          [1, 0, 0],
        ]}
        reverse={{
          enabled: true,
          rate: 2,
          speed: 1,
          color: '#c084fc',
          size: 6,
          brightness: 1,
          maxParticles: 2,
        }}
        random={() => 0.5}
      />
    );

    expect(getAllByTestId('flow-line')).toHaveLength(3);
    expect(renderedFlow.frame).toBeTypeOf('function');

    act(() => {
      renderedFlow.frame?.({}, 0.5);
    });

    expect(renderedFlow.particles).toEqual([
      expect.objectContaining({
        direction: 'reverse',
        color: '#c084fc',
      }),
    ]);
    expect(renderedFlow.particles).not.toContainEqual(
      expect.objectContaining({ direction: 'forward' })
    );
  });
});
