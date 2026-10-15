/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import * as THREE from 'three';
vi.mock('@react-three/drei', async () => {
  const React = await import('react');
  return {
    Html: ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', {}, children),
  };
});
import { SigmetMapLabels } from './SigmetMapLabels';
afterEach(cleanup);
it('registers the current advisory callouts with shared layout and removes them when attention clears', () => {
  const globeOccluder = { current: new THREE.Group() };
  const { container, rerender } = render(
    <SigmetMapLabels
      globeOccluder={globeOccluder}
      labels={[
        {
          id: 'sigmet:one',
          text: 'KZNY R1',
          color: '#7dd3fc',
          position: [2.033, 0, 0],
        },
        {
          id: 'sigmet:two',
          text: 'KZNY B1',
          color: '#f0abfc',
          position: [0, 2.033, 0],
        },
      ]}
    />
  );
  expect(container.querySelectorAll('[data-label-kind="sigmet"]')).toHaveLength(
    2
  );
  expect(screen.getByText('KZNY R1').className).toBe('globe-marker-label');
  expect(screen.getByText('KZNY B1').style.borderColor).toBe(
    'rgb(240, 171, 252)'
  );
  rerender(<SigmetMapLabels globeOccluder={globeOccluder} labels={[]} />);
  expect(container.querySelectorAll('[data-label-kind="sigmet"]')).toHaveLength(
    0
  );
});
